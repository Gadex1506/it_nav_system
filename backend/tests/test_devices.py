"""
Pruebas de integracion del registro de dispositivos (luces y puertas):
crear, listar, renombrar, eliminar, validaciones y cascada.
"""

NODE_PAYLOAD = {
    "house_id": 1, "node_type": "room", "internal_name": "SALA",
    "display_name": "Sala", "unity_x": 0, "unity_y": 0, "unity_z": 0,
}


def _create_node(client, internal_name="SALA", house_id=1):
    payload = {**NODE_PAYLOAD, "internal_name": internal_name, "house_id": house_id}
    response = client.post("/dev/nodes", json=payload)
    assert response.status_code == 201
    return response.json()["id"]


def _device_payload(node_id, key="light_living", device_type="light", name="Luz de la sala"):
    return {"node_id": node_id, "device_type": device_type,
            "device_key": key, "display_name": name}


def test_create_device_returns_201_and_data(client):
    node_id = _create_node(client)
    response = client.post("/dev/devices", json=_device_payload(node_id))
    assert response.status_code == 201
    data = response.json()
    assert data["device_key"] == "light_living" and data["node_id"] == node_id


def test_create_device_requires_dev_key(client):
    node_id = _create_node(client)
    response = client.post("/dev/devices", json=_device_payload(node_id),
                        headers={"X-Dev-Key": ""})
    assert response.status_code == 401


def test_delete_device_requires_dev_key(client):
    node_id = _create_node(client)
    device_id = client.post("/dev/devices", json=_device_payload(node_id)).json()["id"]
    response = client.delete(f"/dev/devices/{device_id}", headers={"X-Dev-Key": "mala"})
    assert response.status_code == 401


def test_create_device_unknown_node_returns_400(client):
    response = client.post("/dev/devices", json=_device_payload(999))
    assert response.status_code == 400


def test_invalid_device_type_returns_422(client):
    node_id = _create_node(client)
    response = client.post("/dev/devices", json=_device_payload(node_id, device_type="fan"))
    assert response.status_code == 422


def test_invalid_device_key_returns_422(client):
    node_id = _create_node(client)
    for bad_key in ("Luz Sala", "luz-sala", "luz.sala", ""):
        response = client.post("/dev/devices", json=_device_payload(node_id, key=bad_key))
        assert response.status_code == 422, bad_key


def test_duplicate_device_key_returns_409(client):
    node_id = _create_node(client)
    assert client.post("/dev/devices", json=_device_payload(node_id)).status_code == 201
    response = client.post("/dev/devices", json=_device_payload(node_id))
    assert response.status_code == 409


def test_list_by_node_and_type_filter(client):
    node_id = _create_node(client)
    client.post("/dev/devices", json=_device_payload(node_id))
    client.post("/dev/devices", json=_device_payload(node_id, "door_living", "door", "Puerta"))
    all_devices = client.get("/dev/devices", params={"node_id": node_id}).json()
    lights = client.get("/dev/devices", params={"node_id": node_id, "device_type": "light"}).json()
    assert len(all_devices) == 2
    assert [d["device_key"] for d in lights] == ["light_living"]


def test_list_by_house_includes_all_rooms(client):
    sala = _create_node(client, "SALA")
    cocina = _create_node(client, "COCINA")
    client.post("/dev/devices", json=_device_payload(sala))
    client.post("/dev/devices", json=_device_payload(cocina, "light_kitchen", "light", "Luz cocina"))
    devices = client.get("/dev/devices", params={"house_id": 1, "device_type": "light"}).json()
    assert {d["device_key"] for d in devices} == {"light_living", "light_kitchen"}


def test_list_requires_exactly_one_scope(client):
    assert client.get("/dev/devices").status_code == 400
    assert client.get("/dev/devices", params={"house_id": 1, "node_id": 1}).status_code == 400


def test_list_with_invalid_type_returns_400(client):
    response = client.get("/dev/devices", params={"house_id": 1, "device_type": "fan"})
    assert response.status_code == 400


def test_rename_changes_display_name_but_not_key(client):
    node_id = _create_node(client)
    device_id = client.post("/dev/devices", json=_device_payload(node_id)).json()["id"]
    response = client.patch(f"/dev/devices/{device_id}/display-name",
                            json={"display_name": "Lampara principal"})
    assert response.status_code == 200
    assert response.json()["display_name"] == "Lampara principal"
    assert response.json()["device_key"] == "light_living"


def test_rename_unknown_device_returns_404(client):
    response = client.patch("/dev/devices/999/display-name", json={"display_name": "X"})
    assert response.status_code == 404


def test_delete_device(client):
    node_id = _create_node(client)
    device_id = client.post("/dev/devices", json=_device_payload(node_id)).json()["id"]
    assert client.delete(f"/dev/devices/{device_id}").status_code == 200
    assert client.get("/dev/devices", params={"node_id": node_id}).json() == []
    assert client.delete(f"/dev/devices/{device_id}").status_code == 404


def test_deleting_node_removes_its_devices(client):
    node_id = _create_node(client)
    client.post("/dev/devices", json=_device_payload(node_id))
    assert client.delete(f"/dev/nodes/{node_id}").status_code == 200
    assert client.get("/dev/devices", params={"house_id": 1}).json() == []


def test_deleting_house_removes_its_devices(client):
    house = client.post("/dev/houses", json={"name": "Otra casa"}).json()["id"]
    node_id = _create_node(client, "SALA2", house_id=house)
    client.post("/dev/devices", json=_device_payload(node_id, "light_other"))
    response = client.delete(f"/dev/houses/{house}", params={"confirm_name": "Otra casa"})
    assert response.status_code == 200

    from app.infrastructure.database import get_db
    remaining = get_db().execute("SELECT COUNT(*) FROM devices").fetchone()[0]
    assert remaining == 0


def test_device_key_is_normalized_in_domain(client):
    from app.domain.models import Device
    device = Device.create(node_id=1, device_type="light", device_key="  Light_Living ", display_name=" Luz ")
    assert device.device_key == "light_living" and device.display_name == "Luz"
