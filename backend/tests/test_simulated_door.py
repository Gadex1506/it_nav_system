"""
tests/test_simulated_door.py

Comportamiento de la puerta simulada (servo) SIN broker: se le pasa una
funcion de publicacion falsa y tiempos muy cortos.
"""

import time

import pytest

from app.infrastructure import mqtt_protocol as proto
from simulator import contract
from simulator.devices import SimulatedDoor

TRAVEL = 0.05
DEFAULT_HOLD = 5.0   # largo a proposito: solo vence si la prueba lo espera
WAIT = 2.0


@pytest.fixture()
def door():
    published = []
    sim = SimulatedDoor("door_banio", TRAVEL, DEFAULT_HOLD)
    sim.bind(lambda key, state: published.append(state))
    sim.published = published
    yield sim
    sim.shutdown()


def _wait_for(door, state, timeout=WAIT):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if door.current_state() == state:
            return True
        time.sleep(0.01)
    return False


def _open(hold_ms=None):
    return proto.encode_door_command("open", hold_ms)


def _close():
    return proto.encode_door_command("close")


# ─── Lectura del contrato (lado dispositivo) ─────────────────────────────

def test_backend_commands_are_understood_by_the_device():
    cmd = contract.parse_door_command(proto.encode_door_command("open", 10000))
    assert (cmd.action, cmd.hold_ms) == ("open", 10000)
    assert contract.parse_door_command(proto.encode_door_command("close")).hold_ms is None


def test_invalid_door_commands_are_ignored():
    for bad in (b"basura", b"[]", b'{"action":5}', b'{"action":"girar"}', b'{"state":"open"}'):
        assert contract.parse_door_command(bad) is None


def test_invalid_hold_ms_is_dropped_but_the_order_survives():
    for bad in (b'{"action":"open","hold_ms":-1}', b'{"action":"open","hold_ms":"10"}',
                b'{"action":"open","hold_ms":true}', b'{"action":"open","hold_ms":0}'):
        cmd = contract.parse_door_command(bad)
        assert cmd is not None and cmd.action == "open" and cmd.hold_ms is None


# ─── Movimiento del servo ────────────────────────────────────────────────

def test_open_goes_through_opening_then_open(door):
    assert door.handle_command(_open()) == "opening"
    assert _wait_for(door, "open")
    assert door.published == ["open"]


def test_close_goes_through_closing_then_closed(door):
    door.handle_command(_open())
    assert _wait_for(door, "open")

    assert door.handle_command(_close()) == "closing"
    assert _wait_for(door, "closed")
    assert door.published == ["open", "closed"]


def test_close_when_already_closed_just_reports_closed(door):
    assert door.handle_command(_close()) == "closed"


def test_open_when_already_open_republishes_open(door):
    door.handle_command(_open())
    assert _wait_for(door, "open")
    assert door.handle_command(_open()) == "open"


def test_hold_ms_closes_the_door_by_itself(door):
    door.handle_command(_open(hold_ms=200))
    assert _wait_for(door, "open")
    assert _wait_for(door, "closed")
    assert door.published == ["open", "closing", "closed"]


def test_default_hold_is_used_when_the_order_has_none():
    short = SimulatedDoor("door_banio", TRAVEL, 0.2)
    short.bind(lambda key, state: None)
    try:
        short.handle_command(_open())
        assert _wait_for(short, "open")
        assert _wait_for(short, "closed")
    finally:
        short.shutdown()


def test_close_order_beats_the_pending_automatic_close(door):
    door.handle_command(_open(hold_ms=300))
    assert _wait_for(door, "open")
    door.handle_command(_close())
    assert _wait_for(door, "closed")
    time.sleep(0.5)  # el hold viejo ya habria vencido: no debe pasar nada raro
    assert door.current_state() == "closed"
    assert door.published == ["open", "closed"]


def test_new_open_restarts_the_safety_timer(door):
    door.handle_command(_open(hold_ms=400))
    assert _wait_for(door, "open")
    time.sleep(0.3)
    door.handle_command(_open(hold_ms=400))   # reinicia la cuenta
    time.sleep(0.25)                          # 0.55 s desde el primer open: ya habria cerrado
    assert door.current_state() == "open"
    assert _wait_for(door, "closed")


def test_reopening_during_closing_cancels_the_close(door):
    door.handle_command(_open())
    assert _wait_for(door, "open")
    door.handle_command(_close())
    assert door.current_state() == "closing"
    assert door.handle_command(_open()) == "opening"
    assert _wait_for(door, "open")
    time.sleep(0.2)
    assert door.current_state() == "open"


def test_shutdown_stops_pending_movement(door):
    door.handle_command(_open())
    door.shutdown()
    time.sleep(0.3)
    assert door.current_state() == "opening"   # sin energia, el servo se queda donde estaba
    assert door.published == []
