"""
tests/test_user_device_commands.py

Endpoints de usuario (/user/devices) que usa Unity. NO piden clave de
desarrollador. Usan la pasarela falsa, asi que no necesitan broker.
"""

NODE_PAYLOAD = {
    "house_id": 1, "node_type": "room", "internal_name": "SALA",
    "display_name": "Sala", "unity_x": 0, "unity_y": 0, "unity_z": 0,
}


def _create_node(client, internal_name="SALA"):
    response = client.post("/dev/nodes", json={**NODE_PAYLOAD, "internal_name": internal_name})
    assert response.status_code == 201
    return response.json()["id"]


def _create_device(client, node_id, key, device_type="light"):
    response = client.post("/dev/devices", json={
        "node_id": node_id, "device_type": device_type,
        "device_key": key, "display_name": key,
    })
    assert response.status_code == 201


def _as_unity(client):
    """Unity no lleva clave de desarrollador."""
    client.headers.pop("X-Dev-Key", None)
    return client


# ─── Una luz ─────────────────────────────────────────────────────────────

def test_one_light_without_dev_key(client, fake_gateway):
    _create_device(client, _create_node(client), "light_sala")

    response = _as_unity(client).post("/user/devices/lights/light_sala", json={"state": "on"})

    assert response.status_code == 202
    assert fake_gateway.published == [("light_sala", "on")]


def test_one_light_normalizes_state(client, fake_gateway):
    _create_device(client, _create_node(client), "light_sala")
    _as_unity(client).post("/user/devices/lights/LIGHT_SALA", json={"state": " OFF "})
    assert fake_gateway.published == [("light_sala", "off")]


def test_one_light_unknown_returns_404(client, fake_gateway):
    assert _as_unity(client).post("/user/devices/lights/light_fantasma",
                                  json={"state": "on"}).status_code == 404


def test_one_light_invalid_state_returns_400(client, fake_gateway):
    _create_device(client, _create_node(client), "light_sala")
    assert _as_unity(client).post("/user/devices/lights/light_sala",
                                  json={"state": "medio"}).status_code == 400
    assert fake_gateway.published == []


def test_one_light_rejects_a_door(client, fake_gateway):
    _create_device(client, _create_node(client), "door_sala", "door")
    assert _as_unity(client).post("/user/devices/lights/door_sala",
                                  json={"state": "on"}).status_code == 400


def test_one_light_without_broker_returns_503(client, fake_gateway):
    _create_device(client, _create_node(client), "light_sala")
    fake_gateway.connected = False
    assert _as_unity(client).post("/user/devices/lights/light_sala",
                                  json={"state": "on"}).status_code == 503


# ─── Todas las luces ─────────────────────────────────────────────────────

def test_all_lights_sends_one_order_per_light_and_no_doors(client, fake_gateway):
    node = _create_node(client)
    _create_device(client, node, "light_sala")
    _create_device(client, node, "light_cocina")
    _create_device(client, node, "door_sala", "door")

    response = _as_unity(client).post("/user/devices/lights", json={"house_id": 1, "state": "off"})

    assert response.status_code == 202
    assert sorted(response.json()["device_keys"]) == ["light_cocina", "light_sala"]
    assert sorted(fake_gateway.published) == [("light_cocina", "off"), ("light_sala", "off")]


def test_all_lights_without_broker_sends_nothing(client, fake_gateway):
    _create_device(client, _create_node(client), "light_sala")
    fake_gateway.connected = False

    response = _as_unity(client).post("/user/devices/lights", json={"house_id": 1, "state": "on"})

    assert response.status_code == 503
    assert fake_gateway.published == []


def test_all_lights_invalid_state_returns_400(client, fake_gateway):
    assert _as_unity(client).post("/user/devices/lights",
                                  json={"house_id": 1, "state": "x"}).status_code == 400


def test_all_lights_invalid_house_id_returns_422(client, fake_gateway):
    assert _as_unity(client).post("/user/devices/lights",
                                  json={"house_id": 0, "state": "on"}).status_code == 422


def test_all_lights_in_a_house_without_lights_returns_empty_list(client, fake_gateway):
    response = _as_unity(client).post("/user/devices/lights", json={"house_id": 1, "state": "on"})
    assert response.status_code == 202
    assert response.json()["device_keys"] == []
