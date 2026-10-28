"""
tests/test_simulator_contract.py

Comprueba que las DOS lecturas independientes del contrato coinciden:
la del backend (app/infrastructure/mqtt_protocol.py) y la del dispositivo
(simulator/contract.py). No necesita broker.
"""

import json

from app.infrastructure import mqtt_protocol
from simulator import contract


def test_topics_match_backend_and_device_sides():
    assert contract.set_topic("light_sala") == mqtt_protocol.light_set_topic("light_sala")


def test_backend_command_is_understood_by_the_device():
    payload = mqtt_protocol.encode_light_command("on")
    assert contract.parse_light_command(payload) == "on"


def test_device_state_is_understood_by_the_backend():
    payload = contract.encode_state("off", 1234)
    report = mqtt_protocol.decode_state_payload("light_sala", payload)
    assert report is not None
    assert report.state == "off"
    assert report.timestamp_ms == 1234


def test_device_ignores_invalid_commands():
    for bad in (b"basura", b"[]", b'{"state":5}', b'{"state":"dim"}', b"\xff\xfe"):
        assert contract.parse_light_command(bad) is None


def test_state_payload_shape():
    data = json.loads(contract.encode_state("on", 10))
    assert data == {"state": "on", "ts_ms": 10}
