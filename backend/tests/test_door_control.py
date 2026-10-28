"""
tests/test_door_control.py

Control de puertas a traves de la pasarela. Usa la pasarela falsa
(fixture fake_gateway), asi que no necesita broker.
"""

import json

from app.infrastructure import mqtt_protocol as proto

NODE_PAYLOAD = {
    "house_id": 1, "node_type": "room", "internal_name": "SALA",
    "display_name": "Sala", "unity_x": 0, "unity_y": 0, "unity_z": 0,
}


def _create_node(client):
    response = client.post("/dev/nodes", json=NODE_PAYLOAD)
    assert response.status_code == 201
    return response.json()["id"]


def _create_device(client, node_id, key, device_type):
    response = client.post("/dev/devices", json={
        "node_id": node_id, "device_type": device_type,
        "device_key": key, "display_name": key,
    })
    assert response.status_code == 201


def _door(client):
    _create_device(client, _create_node(client), "door_cuarto_principal", "door")


# ─── Traductor del contrato ──────────────────────────────────────────────

def test_door_set_topic_matches_contract():
    assert proto.door_set_topic("door_cuarto_principal") == \
        "inclusive/casa1/devices/door_cuarto_principal/set"


def test_encode_door_open_with_hold():
    payload = proto.encode_door_command("open", 10000)
    assert payload == b'{"action":"open","hold_ms":10000}'


def test_encode_door_open_without_hold_omits_the_field():
    assert proto.encode_door_command("open") == b'{"action":"open"}'
    assert json.loads(proto.encode_door_command("close")) == {"action": "close"}


# ─── POST /dev/gateway/doors/{device_key} ────────────────────────────────

def test_open_door_publishes_command_and_returns_202(client, fake_gateway):
    _door(client)

    response = client.post("/dev/gateway/doors/door_cuarto_principal",
                           json={"action": "open", "hold_ms": 10000})

    assert response.status_code == 202
    assert response.json()["requested_action"] == "open"
    assert fake_gateway.published_doors == [("door_cuarto_principal", "open", 10000)]


def test_open_door_without_hold_sends_none(client, fake_gateway):
    _door(client)
    client.post("/dev/gateway/doors/door_cuarto_principal", json={"action": " OPEN "})
    assert fake_gateway.published_doors == [("door_cuarto_principal", "open", None)]


def test_close_door(client, fake_gateway):
    _door(client)
    response = client.post("/dev/gateway/doors/door_cuarto_principal", json={"action": "close"})
    assert response.status_code == 202
    assert fake_gateway.published_doors == [("door_cuarto_principal", "close", None)]


def test_invalid_action_returns_400(client, fake_gateway):
    _door(client)
    response = client.post("/dev/gateway/doors/door_cuarto_principal", json={"action": "girar"})
    assert response.status_code == 400
    assert fake_gateway.published_doors == []


def test_hold_ms_out_of_range_returns_400(client, fake_gateway):
    _door(client)
    for bad in (0, 999, 60001, -5):
        response = client.post("/dev/gateway/doors/door_cuarto_principal",
                               json={"action": "open", "hold_ms": bad})
        assert response.status_code == 400, bad
    assert fake_gateway.published_doors == []


def test_hold_ms_with_close_returns_400(client, fake_gateway):
    _door(client)
    response = client.post("/dev/gateway/doors/door_cuarto_principal",
                           json={"action": "close", "hold_ms": 5000})
    assert response.status_code == 400


def test_unknown_door_returns_404(client, fake_gateway):
    response = client.post("/dev/gateway/doors/door_fantasma", json={"action": "open"})
    assert response.status_code == 404


def test_door_endpoint_rejects_a_light(client, fake_gateway):
    _create_device(client, _create_node(client), "light_sala", "light")
    response = client.post("/dev/gateway/doors/light_sala", json={"action": "open"})
    assert response.status_code == 400
    assert fake_gateway.published_doors == []


def test_light_endpoint_rejects_a_door(client, fake_gateway):
    _door(client)
    response = client.post("/dev/gateway/lights/door_cuarto_principal", json={"state": "on"})
    assert response.status_code == 400


def test_open_door_without_broker_returns_503(client, fake_gateway):
    _door(client)
    fake_gateway.connected = False
    response = client.post("/dev/gateway/doors/door_cuarto_principal", json={"action": "open"})
    assert response.status_code == 503


def test_door_endpoint_requires_dev_key(client):
    client.headers.pop("X-Dev-Key")
    response = client.post("/dev/gateway/doors/door_cuarto_principal", json={"action": "open"})
    assert response.status_code == 401
