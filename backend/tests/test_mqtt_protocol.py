"""
tests/test_mqtt_protocol.py

Pruebas del traductor del contrato MQTT: temas y mensajes.
Son pruebas unitarias puras: no hay broker ni base de datos.
"""

import json

from app.domain.device_events import DeviceAvailabilityReport, DeviceStateReport
from app.infrastructure import mqtt_protocol as proto


def test_light_set_topic_follows_contract():
    assert proto.light_set_topic("light_sala") == "inclusive/casa1/devices/light_sala/set"


def test_subscription_topics_use_single_level_wildcard():
    assert proto.state_subscription_topic() == "inclusive/casa1/devices/+/state"
    assert proto.availability_subscription_topic() == "inclusive/casa1/devices/+/availability"


def test_parse_device_topic_valid():
    parsed = proto.parse_device_topic("inclusive/casa1/devices/light_sala/state")
    assert parsed == ("light_sala", "state")


def test_parse_device_topic_rejects_foreign_or_malformed_topics():
    bad_topics = [
        "otra/raiz/devices/light_sala/state",
        "inclusive/casa1/devices/light_sala",              # falta el nivel final
        "inclusive/casa1/devices/light_sala/state/extra",  # nivel de mas
        "inclusive/casa1/devices/Luz Sala/state",          # clave invalida
        "inclusive/casa1/robots/robot1/state",             # no es un dispositivo fijo
    ]
    for topic in bad_topics:
        assert proto.parse_device_topic(topic) is None, topic


def test_encode_light_command_is_compact_json():
    payload = proto.encode_light_command("on")
    assert payload == b'{"state":"on"}'


def test_decode_state_payload_valid_with_timestamp():
    report = proto.decode_state_payload("light_sala", b'{"state":"on","ts_ms":48213}')
    assert report == DeviceStateReport("light_sala", "on", 48213)


def test_decode_state_payload_without_timestamp_and_normalizes_case():
    report = proto.decode_state_payload("light_sala", b'{"state":" OFF "}')
    assert report == DeviceStateReport("light_sala", "off", None)


def test_decode_state_payload_ignores_invalid_timestamp_types():
    for bad_ts in ('"abc"', "true", "1.5", "null"):
        payload = f'{{"state":"on","ts_ms":{bad_ts}}}'.encode()
        report = proto.decode_state_payload("light_sala", payload)
        assert report is not None and report.timestamp_ms is None, bad_ts


def test_decode_state_payload_rejects_garbage():
    garbage = [b"", b"not json", b"[1,2]", b'{"x":1}', b'{"state":""}',
               b'{"state":5}', b"\xff\xfe"]
    for payload in garbage:
        assert proto.decode_state_payload("light_sala", payload) is None, payload


def test_decode_availability_payload():
    assert proto.decode_availability_payload("light_sala", b"online") == \
        DeviceAvailabilityReport("light_sala", True)
    assert proto.decode_availability_payload("light_sala", b" OFFLINE\n") == \
        DeviceAvailabilityReport("light_sala", False)


def test_decode_availability_payload_rejects_unknown_text():
    assert proto.decode_availability_payload("light_sala", b"maybe") is None
    assert proto.decode_availability_payload("light_sala", b"\xff") is None


def test_command_roundtrip_is_valid_contract_json():
    data = json.loads(proto.encode_light_command("off"))
    assert data == {"state": "off"}
