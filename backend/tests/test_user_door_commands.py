"""
tests/test_user_door_commands.py

Endpoint de usuario para puertas (/user/devices/doors). Lo usa Unity en el
escenario A (sin robot). No pide clave de desarrollador. Usa la pasarela falsa.
"""

NODE_PAYLOAD = {
    "house_id": 1, "node_type": "room", "internal_name": "BANIO",
    "display_name": "Banio", "unity_x": 0, "unity_y": 0, "unity_z": 0,
}


def _create_device(client, key, device_type="door"):
    node = client.post("/dev/nodes", json=NODE_PAYLOAD)
    assert node.status_code == 201
    response = client.post("/dev/devices", json={
        "node_id": node.json()["id"], "device_type": device_type,
        "device_key": key, "display_name": key,
    })
    assert response.status_code == 201


def _as_unity(client):
    client.headers.pop("X-Dev-Key", None)
    return client


def test_open_with_hold_without_dev_key(client, fake_gateway):
    _create_device(client, "door_banio")

    response = _as_unity(client).post("/user/devices/doors/door_banio",
                                      json={"action": "open", "hold_ms": 15000})

    assert response.status_code == 202
    assert fake_gateway.published_doors == [("door_banio", "open", 15000)]


def test_close_has_no_hold(client, fake_gateway):
    _create_device(client, "door_banio")
    _as_unity(client).post("/user/devices/doors/door_banio", json={"action": "close"})
    assert fake_gateway.published_doors == [("door_banio", "close", None)]


def test_invalid_action_and_bad_hold_return_400(client, fake_gateway):
    _create_device(client, "door_banio")
    unity = _as_unity(client)
    assert unity.post("/user/devices/doors/door_banio", json={"action": "x"}).status_code == 400
    assert unity.post("/user/devices/doors/door_banio",
                      json={"action": "open", "hold_ms": 0}).status_code == 400
    assert unity.post("/user/devices/doors/door_banio",
                      json={"action": "close", "hold_ms": 5000}).status_code == 400
    assert fake_gateway.published_doors == []


def test_unknown_door_returns_404(client, fake_gateway):
    assert _as_unity(client).post("/user/devices/doors/door_fantasma",
                                  json={"action": "open"}).status_code == 404


def test_light_is_rejected_by_door_endpoint(client, fake_gateway):
    _create_device(client, "light_banio", "light")
    assert _as_unity(client).post("/user/devices/doors/light_banio",
                                  json={"action": "open"}).status_code == 400


def test_without_broker_returns_503(client, fake_gateway):
    _create_device(client, "door_banio")
    fake_gateway.connected = False
    assert _as_unity(client).post("/user/devices/doors/door_banio",
                                  json={"action": "open"}).status_code == 503
