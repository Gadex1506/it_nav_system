"""
tests/test_board_availability.py

Contrato v0.3: la disponibilidad de los dispositivos de la casa depende
de su PLACA (un Last Will por placa). No necesita broker.
"""

from app.application.device_state_store import DeviceStateStore
from app.domain.device_events import (
    BoardAvailabilityReport,
    DeviceAvailabilityReport,
    DeviceStateReport,
)
from app.infrastructure import mqtt_protocol as proto

BOARD = "casa"


def _store_with_light(key="light_sala"):
    store = DeviceStateStore()
    store.update_state(DeviceStateReport(key, "on", 1))
    return store


# ─── Traductor del contrato ──────────────────────────────────────────────

def test_board_subscription_topic():
    assert proto.board_availability_subscription_topic() == "inclusive/casa1/boards/+/availability"


def test_parse_board_topic():
    assert proto.parse_board_topic("inclusive/casa1/boards/casa/availability") == ("casa", "availability")


def test_parse_board_topic_rejects_other_shapes():
    assert proto.parse_board_topic("inclusive/casa1/devices/light_sala/state") is None
    assert proto.parse_board_topic("inclusive/casa1/boards/casa") is None
    assert proto.parse_board_topic("inclusive/casa1/boards/CASA/availability") is None


def test_decode_board_availability():
    assert proto.decode_board_availability_payload(BOARD, b"online") == BoardAvailabilityReport(BOARD, True)
    assert proto.decode_board_availability_payload(BOARD, b"offline") == BoardAvailabilityReport(BOARD, False)
    assert proto.decode_board_availability_payload(BOARD, b"quizas") is None


# ─── Regla de conexion del almacen ───────────────────────────────────────

def test_unknown_board_and_no_device_notice_means_unknown():
    assert _store_with_light().get("light_sala").online is None


def test_board_online_makes_devices_online():
    store = _store_with_light()
    store.update_board_availability(BoardAvailabilityReport(BOARD, True))
    assert store.get("light_sala").online is True


def test_board_offline_overrides_everything():
    store = _store_with_light()
    store.update_availability(DeviceAvailabilityReport("light_sala", True))
    store.update_board_availability(BoardAvailabilityReport(BOARD, False))
    assert store.get("light_sala").online is False


def test_one_board_drop_takes_down_all_devices():
    store = _store_with_light("light_sala")
    store.update_state(DeviceStateReport("door_cuarto", "closed", 2))
    store.update_board_availability(BoardAvailabilityReport(BOARD, True))
    store.update_board_availability(BoardAvailabilityReport(BOARD, False))
    assert [s.online for s in store.get_all()] == [False, False]


def test_device_own_offline_notice_is_respected_when_board_online():
    store = _store_with_light()
    store.update_board_availability(BoardAvailabilityReport(BOARD, True))
    store.update_availability(DeviceAvailabilityReport("light_sala", False))
    assert store.get("light_sala").online is False


def test_board_report_reaches_store_through_gateway(fake_gateway, client):
    fake_gateway.emit_state(DeviceStateReport("light_sala", "on", 5))
    fake_gateway.emit_board_availability(BoardAvailabilityReport(BOARD, False))
    response = client.get("/dev/gateway/devices/light_sala/status")
    assert response.status_code == 200
    assert response.json()["online"] is False