"""
tests/test_simulator_integration.py

Backend REAL (MqttDeviceGateway + DeviceStateStore) hablando con una
luz SIMULADA a traves de un broker MQTT real. Es la prueba manual del
paso 2.1b, automatizada. Se omite sola sin broker (ver test_mqtt_integration.py
para las variables INCLUSIVE_TEST_MQTT_*).
"""

import os
import time
import uuid

import pytest

from app.application.device_state_store import DeviceStateStore
from app.infrastructure.mqtt_device_gateway import MqttDeviceGateway
from app.infrastructure.mqtt_settings import MqttSettings
from simulator.devices import SimulatedBoard, SimulatedLight
from simulator.settings import SimulatorSettings

HOST = os.getenv("INCLUSIVE_TEST_MQTT_HOST")
PORT = int(os.getenv("INCLUSIVE_TEST_MQTT_PORT", "1883"))
WAIT_SECONDS = 5
FAST_LATENCY_SECONDS = 0.05

pytestmark = pytest.mark.skipif(not HOST, reason="Sin broker de pruebas (INCLUSIVE_TEST_MQTT_HOST)")


def _wait_until(condition, timeout=WAIT_SECONDS):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return False


def _clear_retained(device_key):
    """Borra los mensajes retenidos de la luz para no ensuciar el broker."""
    import paho.mqtt.client as mqtt
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"clean-{device_key}")
    client.username_pw_set(os.getenv("INCLUSIVE_TEST_MQTT_ESP_USER", ""),
                        os.getenv("INCLUSIVE_TEST_MQTT_ESP_PASSWORD", ""))
    client.connect(HOST, PORT)
    client.loop_start()
    for kind in ("state", "availability"):
        client.publish(f"inclusive/casa1/devices/{device_key}/{kind}", b"", qos=1, retain=True).wait_for_publish(2)
    client.loop_stop()
    client.disconnect()


@pytest.fixture()
def device_key():
    # Clave unica por prueba: evita choques con mensajes retenidos de otras
    key = f"light_t{uuid.uuid4().hex[:8]}"
    yield key
    _clear_retained(key)


@pytest.fixture()
def backend():
    store = DeviceStateStore()
    gateway = MqttDeviceGateway(MqttSettings(
        host=HOST, port=PORT,
        username=os.getenv("INCLUSIVE_TEST_MQTT_BACKEND_USER", ""),
        password=os.getenv("INCLUSIVE_TEST_MQTT_BACKEND_PASSWORD", ""),
        client_id=f"backend-{uuid.uuid4().hex[:6]}", keepalive_seconds=10, qos=1,
        reconnect_min_seconds=1, reconnect_max_seconds=2))
    gateway.set_state_listener(store.update_state)
    gateway.set_availability_listener(store.update_availability)
    gateway.set_board_availability_listener(store.update_board_availability)
    gateway.start()
    assert _wait_until(lambda: gateway.is_connected)
    yield gateway, store
    gateway.stop()


def _sim_settings():
    return SimulatorSettings(
        host=HOST, port=PORT,
        username=os.getenv("INCLUSIVE_TEST_MQTT_ESP_USER", ""),
        password=os.getenv("INCLUSIVE_TEST_MQTT_ESP_PASSWORD", ""),
        latency_seconds=FAST_LATENCY_SECONDS)


def _new_board(*device_keys):
    return SimulatedBoard("casa", [SimulatedLight(k) for k in device_keys], _sim_settings())


def _is_online(store, key):
    status = store.get(key)
    return status is not None and status.online is True


@pytest.fixture(autouse=True)
def _clean_board_topic():
    """El tema de la placa es compartido: se limpia antes y despues de cada prueba."""
    _clear_board()
    yield
    _clear_board()


def _clear_board():
    import paho.mqtt.client as mqtt
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="clean-board")
    client.username_pw_set(os.getenv("INCLUSIVE_TEST_MQTT_ESP_USER", ""),
                        os.getenv("INCLUSIVE_TEST_MQTT_ESP_PASSWORD", ""))
    client.connect(HOST, PORT)
    client.loop_start()
    client.publish("inclusive/casa1/boards/casa/availability", b"", qos=1, retain=True).wait_for_publish(2)
    client.loop_stop()
    client.disconnect()


def test_order_reaches_simulated_light_and_state_comes_back(backend, device_key):
    gateway, store = backend
    board = _new_board(device_key)
    board.start()
    try:
        assert _wait_until(lambda: _is_online(store, device_key))
        gateway.publish_light_command(device_key, "on")
        assert _wait_until(lambda: store.get(device_key).state == "on")
    finally:
        board.stop()


def test_graceful_stop_reports_offline(backend, device_key):
    _, store = backend
    board = _new_board(device_key)
    board.start()
    assert _wait_until(lambda: _is_online(store, device_key))
    board.stop()
    assert _wait_until(lambda: store.get(device_key).online is False)


def test_power_cut_takes_down_ALL_devices_with_one_last_will(backend, device_key):
    """Una sola caida de placa debe marcar offline a todas sus luces."""
    _, store = backend
    other_key = device_key + "b"
    board = _new_board(device_key, other_key)
    board.start()
    assert _wait_until(lambda: _is_online(store, device_key) and _is_online(store, other_key))

    board.simulate_power_cut()

    assert _wait_until(lambda: store.get(device_key).online is False
                    and store.get(other_key).online is False)
    _clear_retained(other_key)


# ─── Puertas ─────────────────────────────────────────────────────────────

def _new_board_with_door(door_key, travel=0.05):
    from simulator.devices import SimulatedDoor
    return SimulatedBoard("casa", [SimulatedDoor(door_key, travel, 5.0)], _sim_settings())


def _state_of(store, key):
    status = store.get(key)
    return None if status is None else status.state


def test_door_order_reaches_simulated_door_and_state_returns(backend, device_key):
    gateway, store = backend
    door_key = device_key.replace("light_", "door_")
    board = _new_board_with_door(door_key)
    board.start()
    try:
        assert _wait_until(lambda: _state_of(store, door_key) == "closed")

        gateway.publish_door_command(door_key, "open", 10000)
        assert _wait_until(lambda: _state_of(store, door_key) == "open")

        gateway.publish_door_command(door_key, "close")
        assert _wait_until(lambda: _state_of(store, door_key) == "closed")
    finally:
        board.stop()
        _clear_retained(door_key)


def test_door_hold_ms_closes_it_without_a_close_order(backend, device_key):
    gateway, store = backend
    door_key = device_key.replace("light_", "door_")
    board = _new_board_with_door(door_key)
    board.start()
    try:
        assert _wait_until(lambda: _state_of(store, door_key) == "closed")
        gateway.publish_door_command(door_key, "open", 400)
        assert _wait_until(lambda: _state_of(store, door_key) == "open")
        assert _wait_until(lambda: _state_of(store, door_key) == "closed", timeout=3)
    finally:
        board.stop()
        _clear_retained(door_key)