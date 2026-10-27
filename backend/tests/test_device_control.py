"""
tests/test_device_control.py

Pruebas de integracion del control de luces a traves de la pasarela.
Usa la pasarela falsa (fixture fake_gateway), asi que no necesita broker.
"""

from app.application.device_control_service import DeviceControlService
from app.application.device_state_store import DeviceStateStore
from app.domain.device_events import DeviceAvailabilityReport, DeviceStateReport

NODE_PAYLOAD = {
    "house_id": 1, "node_type": "room", "internal_name": "SALA",
    "display_name": "Sala", "unity_x": 0, "unity_y": 0, "unity_z": 0,
}


def _create_node(client, internal_name="SALA"):
    payload = {**NODE_PAYLOAD, "internal_name": internal_name}
    response = client.post("/dev/nodes", json=payload)
    assert response.status_code == 201
    return response.json()["id"]


def _create_device(client, node_id, key="light_sala", device_type="light"):
    response = client.post("/dev/devices", json={
        "node_id": node_id, "device_type": device_type,
        "device_key": key, "display_name": key,
    })
    assert response.status_code == 201


# ─── POST /dev/gateway/lights/{device_key} ───────────────────────────────

def test_set_light_publishes_command_and_returns_202(client, fake_gateway):
    _create_device(client, _create_node(client))

    response = client.post("/dev/gateway/lights/light_sala", json={"state": "on"})

    assert response.status_code == 202
    assert response.json()["requested_state"] == "on"
    assert fake_gateway.published == [("light_sala", "on")]


def test_set_light_normalizes_state_and_key(client, fake_gateway):
    _create_device(client, _create_node(client))

    response = client.post("/dev/gateway/lights/LIGHT_SALA", json={"state": " OFF "})

    assert response.status_code == 202
    assert fake_gateway.published == [("light_sala", "off")]


def test_set_light_unknown_device_returns_404(client, fake_gateway):
    response = client.post("/dev/gateway/lights/light_fantasma", json={"state": "on"})
    assert response.status_code == 404
    assert fake_gateway.published == []


def test_set_light_on_a_door_returns_400(client, fake_gateway):
    _create_device(client, _create_node(client), key="door_sala", device_type="door")

    response = client.post("/dev/gateway/lights/door_sala", json={"state": "on"})

    assert response.status_code == 400
    assert fake_gateway.published == []


def test_set_light_invalid_state_returns_400(client, fake_gateway):
    _create_device(client, _create_node(client))

    response = client.post("/dev/gateway/lights/light_sala", json={"state": "brillante"})

    assert response.status_code == 400
    assert fake_gateway.published == []


def test_set_light_without_broker_returns_503(client, fake_gateway):
    _create_device(client, _create_node(client))
    fake_gateway.connected = False

    response = client.post("/dev/gateway/lights/light_sala", json={"state": "on"})

    assert response.status_code == 503


def test_gateway_endpoints_require_dev_key(client):
    no_key = {"X-Dev-Key": ""}
    assert client.post("/dev/gateway/lights/x", json={"state": "on"}, headers=no_key).status_code == 401
    assert client.get("/dev/gateway/status", headers=no_key).status_code == 401


# ─── Estado que reportan los dispositivos ────────────────────────────────

def test_status_reflects_device_reports(client, fake_gateway):
    fake_gateway.emit_state(DeviceStateReport("light_sala", "on", 100))
    fake_gateway.emit_availability(DeviceAvailabilityReport("light_sala", True))

    response = client.get("/dev/gateway/devices/light_sala/status")

    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "on" and data["online"] is True
    assert data["last_update"] is not None


def test_status_unknown_device_returns_404(client):
    assert client.get("/dev/gateway/devices/light_nunca/status").status_code == 404


def test_gateway_status_lists_connection_and_devices(client, fake_gateway):
    fake_gateway.emit_state(DeviceStateReport("light_sala", "off"))

    data = client.get("/dev/gateway/status").json()

    assert data["connected"] is True
    assert [d["device_key"] for d in data["devices"]] == ["light_sala"]


def test_offline_report_keeps_last_known_state(client, fake_gateway):
    fake_gateway.emit_state(DeviceStateReport("light_sala", "on"))
    fake_gateway.emit_availability(DeviceAvailabilityReport("light_sala", False))

    data = client.get("/dev/gateway/devices/light_sala/status").json()

    assert data["online"] is False and data["state"] == "on"


def test_app_lifecycle_starts_and_stops_the_gateway(client, fake_gateway):
    # El lifespan de la app ya llamo a start; el stop ocurre al salir del TestClient
    assert fake_gateway.started is True


# ─── Servicio: todas las luces ───────────────────────────────────────────

def _control_service(client, fake_gateway):
    from app.presentation.routers.dev_router import get_device_service
    return DeviceControlService(get_device_service(), fake_gateway, DeviceStateStore())


def test_set_all_lights_sends_only_lights_of_the_house(client, fake_gateway):
    node_id = _create_node(client)
    _create_device(client, node_id, "light_sala")
    _create_device(client, node_id, "light_sala_2")
    _create_device(client, node_id, "door_sala", "door")

    sent = _control_service(client, fake_gateway).set_all_lights(1, "off")

    assert sorted(sent) == ["light_sala", "light_sala_2"]
    assert sorted(fake_gateway.published) == [("light_sala", "off"), ("light_sala_2", "off")]


def test_set_all_lights_without_broker_sends_nothing(client, fake_gateway):
    import pytest
    from app.domain.exceptions import GatewayUnavailableError

    node_id = _create_node(client)
    _create_device(client, node_id, "light_sala")
    fake_gateway.connected = False

    with pytest.raises(GatewayUnavailableError):
        _control_service(client, fake_gateway).set_all_lights(1, "on")

    assert fake_gateway.published == []


def test_set_all_lights_with_no_lights_returns_empty_list(client, fake_gateway):
    assert _control_service(client, fake_gateway).set_all_lights(1, "on") == []
