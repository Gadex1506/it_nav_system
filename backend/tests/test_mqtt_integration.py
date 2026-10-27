"""
tests/test_mqtt_integration.py

Prueba de integracion de MqttDeviceGateway contra un broker MQTT REAL.

Se OMITE sola si no hay broker configurado, asi `pytest -q` normal no
depende de Mosquitto. Para ejecutarla, define antes estas variables:

    INCLUSIVE_TEST_MQTT_HOST       (ej: localhost)
    INCLUSIVE_TEST_MQTT_PORT       (opcional, por defecto 1883)
    INCLUSIVE_TEST_MQTT_BACKEND_USER / INCLUSIVE_TEST_MQTT_BACKEND_PASSWORD
    INCLUSIVE_TEST_MQTT_ESP_USER     / INCLUSIVE_TEST_MQTT_ESP_PASSWORD

El "ESP32" de la prueba es un cliente paho que se hace pasar por la
placa: recibe la orden en el tema /set y responde en /state.
"""

import os
import queue
import time

import paho.mqtt.client as mqtt
import pytest

from app.domain.exceptions import GatewayUnavailableError
from app.infrastructure.mqtt_device_gateway import MqttDeviceGateway
from app.infrastructure.mqtt_settings import MqttSettings

HOST = os.getenv("INCLUSIVE_TEST_MQTT_HOST")
PORT = int(os.getenv("INCLUSIVE_TEST_MQTT_PORT", "1883"))
WAIT_SECONDS = 5

pytestmark = pytest.mark.skipif(not HOST, reason="Sin broker de pruebas (INCLUSIVE_TEST_MQTT_HOST)")


def _settings(user_env: str, password_env: str, client_id: str) -> MqttSettings:
    return MqttSettings(
        host=HOST, port=PORT,
        username=os.getenv(user_env, ""), password=os.getenv(password_env, ""),
        client_id=client_id, keepalive_seconds=10, qos=1,
        reconnect_min_seconds=1, reconnect_max_seconds=2,
    )


def _wait_until(condition, timeout=WAIT_SECONDS):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture()
def gateway():
    received_states, received_availability = [], []
    gw = MqttDeviceGateway(_settings(
        "INCLUSIVE_TEST_MQTT_BACKEND_USER", "INCLUSIVE_TEST_MQTT_BACKEND_PASSWORD",
        "inclusive-backend-test"))
    gw.set_state_listener(received_states.append)
    gw.set_availability_listener(received_availability.append)
    gw.start()
    assert _wait_until(lambda: gw.is_connected), "El gateway no se conecto al broker"
    gw.received_states, gw.received_availability = received_states, received_availability
    yield gw
    gw.stop()


@pytest.fixture()
def fake_esp32():
    """Cliente paho que hace de ESP32: guarda las ordenes que le llegan."""
    commands = queue.Queue()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="esp32-test")
    client.username_pw_set(os.getenv("INCLUSIVE_TEST_MQTT_ESP_USER", ""),
                           os.getenv("INCLUSIVE_TEST_MQTT_ESP_PASSWORD", ""))
    client.on_connect = lambda c, u, f, rc, p: c.subscribe("inclusive/casa1/devices/+/set", qos=1)
    client.on_message = lambda c, u, m: commands.put((m.topic, m.payload))
    client.connect(HOST, PORT)
    client.loop_start()
    time.sleep(0.5)
    client.commands = commands
    yield client
    client.loop_stop()
    client.disconnect()


def test_command_reaches_esp32_with_contract_topic_and_payload(gateway, fake_esp32):
    gateway.publish_light_command("light_sala", "on")

    topic, payload = fake_esp32.commands.get(timeout=WAIT_SECONDS)

    assert topic == "inclusive/casa1/devices/light_sala/set"
    assert payload == b'{"state":"on"}'


def test_state_and_availability_from_esp32_reach_listeners(gateway, fake_esp32):
    fake_esp32.publish("inclusive/casa1/devices/light_sala/availability", "online", qos=1, retain=True)
    fake_esp32.publish("inclusive/casa1/devices/light_sala/state",
                       '{"state":"on","ts_ms":48213}', qos=1, retain=True)

    assert _wait_until(lambda: gateway.received_states and gateway.received_availability)
    assert gateway.received_states[-1].state == "on"
    assert gateway.received_states[-1].timestamp_ms == 48213
    assert gateway.received_availability[-1].online is True

    # Dejar el broker limpio (borra los mensajes retenidos de la prueba)
    fake_esp32.publish("inclusive/casa1/devices/light_sala/availability", b"", qos=1, retain=True)
    fake_esp32.publish("inclusive/casa1/devices/light_sala/state", b"", qos=1, retain=True)


def test_garbage_message_does_not_kill_the_gateway(gateway, fake_esp32):
    fake_esp32.publish("inclusive/casa1/devices/light_sala/state", "esto no es json", qos=1)
    fake_esp32.publish("inclusive/casa1/devices/light_sala/state", '{"state":"off"}', qos=1)

    assert _wait_until(lambda: gateway.received_states)
    assert gateway.received_states[-1].state == "off"
    assert gateway.is_connected


def test_wrong_password_never_connects_and_orders_are_rejected():
    bad = MqttDeviceGateway(MqttSettings(
        host=HOST, port=PORT, username="inclusive_backend", password="clave_incorrecta",
        client_id="inclusive-backend-bad", keepalive_seconds=10, qos=1,
        reconnect_min_seconds=1, reconnect_max_seconds=2))
    bad.start()
    try:
        time.sleep(1.5)
        assert bad.is_connected is False
        with pytest.raises(GatewayUnavailableError):
            bad.publish_light_command("light_sala", "on")
    finally:
        bad.stop()
