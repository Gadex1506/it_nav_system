"""
tests/test_order_tracker.py

Seguimiento de ordenes (luces y puertas) con un reloj falso: sin esperar de verdad.
"""

import pytest

from app.application.order_tracker import OrderTracker
from app.domain.device_events import DeviceStateReport
from app.domain.order_tracking import OrderOutcome


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture()
def clock():
    return FakeClock()


@pytest.fixture()
def tracker(clock):
    return OrderTracker(clock=clock)


def _light(tracker, key="light_sala", state="on", timeout=3.0):
    opposite = "off" if state == "on" else "on"
    tracker.register(key, state, (state,), (opposite,), timeout)


def _door_open(tracker, key="door_banio", timeout=10.0):
    tracker.register(key, "open", ("opening", "open"), ("blocked",), timeout)


def _state(tracker, key, state):
    tracker.on_state(DeviceStateReport(key, state, 1))


def test_no_order_means_none(tracker):
    assert tracker.get("light_sala") is None


def test_new_order_is_pending(tracker):
    _light(tracker)
    assert tracker.get("light_sala").outcome == OrderOutcome.PENDING


def test_expected_state_confirms_the_order(tracker):
    _light(tracker, state="on")
    _state(tracker, "light_sala", "on")
    order = tracker.get("light_sala")
    assert order.outcome == OrderOutcome.CONFIRMED and order.reported_state == "on"


def test_no_state_after_timeout_is_no_response(tracker, clock):
    _light(tracker, timeout=3.0)
    clock.advance(2.9)
    assert tracker.get("light_sala").outcome == OrderOutcome.PENDING
    clock.advance(0.2)
    assert tracker.get("light_sala").outcome == OrderOutcome.NO_RESPONSE


def test_opposite_state_is_a_mismatch(tracker):
    _light(tracker, state="on")
    _state(tracker, "light_sala", "off")
    assert tracker.get("light_sala").outcome == OrderOutcome.MISMATCH


def test_late_state_still_confirms(tracker, clock):
    _light(tracker, state="on", timeout=3.0)
    clock.advance(5)
    assert tracker.get("light_sala").outcome == OrderOutcome.NO_RESPONSE
    _state(tracker, "light_sala", "on")
    assert tracker.get("light_sala").outcome == OrderOutcome.CONFIRMED


def test_confirmed_order_is_not_changed_by_later_states(tracker):
    _light(tracker, state="on")
    _state(tracker, "light_sala", "on")
    _state(tracker, "light_sala", "off")   # alguien la apago a mano despues: ya no es de esta orden
    assert tracker.get("light_sala").outcome == OrderOutcome.CONFIRMED


def test_new_order_replaces_the_previous_one(tracker):
    _light(tracker, state="on")
    first = tracker.get("light_sala").order_id
    _light(tracker, state="off")
    assert tracker.get("light_sala").order_id > first


def test_state_of_another_device_does_not_resolve_the_order(tracker):
    _light(tracker, "light_sala", "on")
    _state(tracker, "light_cocina", "on")
    assert tracker.get("light_sala").outcome == OrderOutcome.PENDING


# ─── Puertas ─────────────────────────────────────────────────────────────

def test_door_opening_confirms_an_open_order(tracker):
    _door_open(tracker)
    _state(tracker, "door_banio", "opening")
    assert tracker.get("door_banio").outcome == OrderOutcome.CONFIRMED


def test_door_blocked_is_a_mismatch(tracker):
    _door_open(tracker)
    _state(tracker, "door_banio", "blocked")
    assert tracker.get("door_banio").outcome == OrderOutcome.MISMATCH


def test_old_closing_state_is_ignored_while_waiting_for_open(tracker):
    _door_open(tracker)
    _state(tracker, "door_banio", "closing")   # transicion vieja, no es respuesta a esta orden
    assert tracker.get("door_banio").outcome == OrderOutcome.PENDING


def test_door_gets_a_longer_timeout_than_a_light(tracker, clock):
    _light(tracker, timeout=3.0)
    _door_open(tracker, timeout=10.0)
    clock.advance(5)
    assert tracker.get("light_sala").outcome == OrderOutcome.NO_RESPONSE
    assert tracker.get("door_banio").outcome == OrderOutcome.PENDING


# ─── Problemas recientes ─────────────────────────────────────────────────

def test_problems_list_only_failures(tracker, clock):
    _light(tracker, "light_sala", "on")            # sin respuesta
    _light(tracker, "light_cocina", "on")          # confirmada
    _light(tracker, "light_comedor", "on")         # estado contrario
    _state(tracker, "light_cocina", "on")
    _state(tracker, "light_comedor", "off")
    clock.advance(4)

    problems = tracker.get_recent_problems(60)

    assert [(p.device_key, p.outcome) for p in problems] == [
        ("light_sala", OrderOutcome.NO_RESPONSE),
        ("light_comedor", OrderOutcome.MISMATCH),
    ]


def test_old_problems_are_hidden(tracker, clock):
    _light(tracker)
    clock.advance(100)
    assert tracker.get_recent_problems(60) == []


def test_pending_orders_are_not_problems(tracker):
    _light(tracker)
    assert tracker.get_recent_problems(60) == []
