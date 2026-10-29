"""
tests/test_order_tracking_api.py

El seguimiento de ordenes de punta a punta por la API, con la pasarela
falsa: se da una orden, se "simula" lo que contaria el ESP32 y se consulta.
"""

import pytest

from app.domain.device_events import DeviceStateReport
from app.infrastructure import gateway_provider

NODE_PAYLOAD = {
    "house_id": 1, "node_type": "room", "internal_name": "SALA",
    "display_name": "Sala", "unity_x": 0, "unity_y": 0, "unity_z": 0,
}


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture()
def clock(client):
    fake = FakeClock()
    gateway_provider.get_order_tracker()._clock = fake
    return fake


def _create_device(client, key, device_type):
    node = client.post("/dev/nodes", json={**NODE_PAYLOAD, "internal_name": key.upper()})
    assert node.status_code == 201
    response = client.post("/dev/devices", json={
        "node_id": node.json()["id"], "device_type": device_type,
        "device_key": key, "display_name": key,
    })
    assert response.status_code == 201


def _last_order(client, key):
    return client.get(f"/dev/gateway/devices/{key}/status").json()["last_order"]


def test_confirmed_light_order_shows_in_device_status(client, fake_gateway, clock):
    _create_device(client, "light_sala", "light")
    client.post("/dev/gateway/lights/light_sala", json={"state": "on"})

    fake_gateway.emit_state(DeviceStateReport("light_sala", "on", 5))

    order = _last_order(client, "light_sala")
    assert order["outcome"] == "confirmed" and order["requested"] == "on"


def test_light_without_answer_becomes_no_response_after_3_seconds(client, fake_gateway, clock):
    _create_device(client, "light_sala", "light")
    fake_gateway.emit_state(DeviceStateReport("light_sala", "off", 1))   # para que exista su estado
    client.post("/dev/gateway/lights/light_sala", json={"state": "on"})

    clock.now += 2
    assert _last_order(client, "light_sala")["outcome"] == "pending"
    clock.now += 1.5
    assert _last_order(client, "light_sala")["outcome"] == "no_response"


def test_door_without_answer_waits_10_seconds(client, fake_gateway, clock):
    _create_device(client, "door_banio", "door")
    fake_gateway.emit_state(DeviceStateReport("door_banio", "closed", 1))
    client.post("/dev/gateway/doors/door_banio", json={"action": "open"})

    clock.now += 5
    assert _last_order(client, "door_banio")["outcome"] == "pending"
    clock.now += 6
    assert _last_order(client, "door_banio")["outcome"] == "no_response"


def test_door_opening_state_confirms_the_order(client, fake_gateway, clock):
    _create_device(client, "door_banio", "door")
    client.post("/dev/gateway/doors/door_banio", json={"action": "open"})
    fake_gateway.emit_state(DeviceStateReport("door_banio", "opening", 1))
    fake_gateway.emit_state(DeviceStateReport("door_banio", "open", 2))
    assert _last_order(client, "door_banio")["outcome"] == "confirmed"


def test_problems_endpoint_for_unity_needs_no_dev_key(client, fake_gateway, clock):
    _create_device(client, "light_sala", "light")
    client.post("/dev/gateway/lights/light_sala", json={"state": "on"})
    clock.now += 4

    client.headers.pop("X-Dev-Key")
    response = client.get("/user/devices/orders/problems")

    assert response.status_code == 200
    problems = response.json()
    assert [(p["device_key"], p["outcome"]) for p in problems] == [("light_sala", "no_response")]
    assert problems[0]["order_id"] >= 1 and problems[0]["detail"]


def test_problems_endpoint_is_empty_when_everything_responded(client, fake_gateway, clock):
    _create_device(client, "light_sala", "light")
    client.post("/dev/gateway/lights/light_sala", json={"state": "on"})
    fake_gateway.emit_state(DeviceStateReport("light_sala", "on", 5))
    clock.now += 4

    client.headers.pop("X-Dev-Key")
    assert client.get("/user/devices/orders/problems").json() == []


def test_user_order_from_unity_is_tracked_too(client, fake_gateway, clock):
    _create_device(client, "light_sala", "light")
    client.headers.pop("X-Dev-Key")
    client.post("/user/devices/lights/light_sala", json={"state": "on"})
    clock.now += 4
    assert len(client.get("/user/devices/orders/problems").json()) == 1


def test_all_lights_order_tracks_every_light(client, fake_gateway, clock):
    _create_device(client, "light_sala", "light")
    _create_device(client, "light_cocina", "light")
    client.post("/user/devices/lights", json={"house_id": 1, "state": "off"})
    fake_gateway.emit_state(DeviceStateReport("light_sala", "off", 1))   # solo una responde
    clock.now += 4

    problems = client.get("/user/devices/orders/problems").json()
    assert [p["device_key"] for p in problems] == ["light_cocina"]


def test_problems_endpoint_in_dev_requires_the_key(client):
    client.headers.pop("X-Dev-Key")
    assert client.get("/dev/gateway/orders/problems").status_code == 401
