"""
simulator/contract.py

El contrato MQTT visto desde el lado del DISPOSITIVO.

Es una copia INDEPENDIENTE a proposito: no importa nada de app/. Si el
simulador reutilizara el traductor del backend, un error de contrato
estaria en los dos lados y las pruebas no lo detectarian. Asi, cada
lado interpreta el contrato por su cuenta y las pruebas de integracion
comparan ambas lecturas. (Analogia: dos traductores que no se consultan
entre si; si coinciden, el mensaje esta bien definido.)

Si el contrato cambia, hay que actualizar este archivo Y
app/infrastructure/mqtt_protocol.py.
"""

import json
from dataclasses import dataclass
from typing import Optional

ROOT = "inclusive/casa1"
DEVICES_SEGMENT = "devices"
BOARDS_SEGMENT = "boards"
HOUSE_BOARD_ID = "casa"   # Placa que maneja luces y puertas (contrato v0.3)

STATE_ON = "on"
STATE_OFF = "off"
VALID_LIGHT_COMMANDS = (STATE_ON, STATE_OFF)

AVAILABILITY_ONLINE = "online"
AVAILABILITY_OFFLINE = "offline"

DOOR_CLOSED = "closed"
DOOR_OPENING = "opening"
DOOR_OPEN = "open"
DOOR_CLOSING = "closing"
DOOR_BLOCKED = "blocked"   # Reservado: aun no se simula

ACTION_OPEN = "open"
ACTION_CLOSE = "close"
VALID_DOOR_ACTIONS = (ACTION_OPEN, ACTION_CLOSE)

FIELD_ACTION = "action"
FIELD_HOLD_MS = "hold_ms"
FIELD_STATE = "state"
FIELD_TIMESTAMP = "ts_ms"


def _device_topic(device_key: str, kind: str) -> str:
    return f"{ROOT}/{DEVICES_SEGMENT}/{device_key}/{kind}"


def set_topic(device_key: str) -> str:
    """Tema donde el dispositivo recibe ordenes."""
    return _device_topic(device_key, "set")


def state_topic(device_key: str) -> str:
    """Tema donde el dispositivo cuenta como quedo."""
    return _device_topic(device_key, "state")


def availability_topic(device_key: str) -> str:
    """Tema donde se anuncia online/offline (con Last Will)."""
    return _device_topic(device_key, "availability")


def board_availability_topic(board_id: str) -> str:
    """Tema donde la PLACA anuncia online/offline (lleva el Last Will)."""
    return f"{ROOT}/{BOARDS_SEGMENT}/{board_id}/availability"


def encode_state(state: str, timestamp_ms: int) -> bytes:
    """Construye el estado que publica el dispositivo: {"state":"on","ts_ms":1000}."""
    payload = {FIELD_STATE: state, FIELD_TIMESTAMP: timestamp_ms}
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def parse_light_command(payload: bytes) -> Optional[str]:
    """
    Interpreta la orden que recibe una luz.

    Un ESP32 real no debe romperse por un mensaje raro: si el mensaje
    no es valido se devuelve None y se ignora.

    Returns:
        'on' u 'off', o None si el mensaje no es una orden valida.
    """
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None

    if not isinstance(data, dict):
        return None

    state = data.get(FIELD_STATE)

    if not isinstance(state, str):
        return None

    normalized = state.strip().lower()
    return normalized if normalized in VALID_LIGHT_COMMANDS else None


@dataclass(frozen=True)
class DoorCommand:
    """
    Orden que recibe una puerta.

    Attributes:
        action: 'open' o 'close'.
        hold_ms: Cierre de seguridad pedido, o None si no vino (la puerta usa el suyo).
    """

    action: str
    hold_ms: Optional[int] = None


def parse_door_command(payload: bytes) -> Optional[DoorCommand]:
    """
    Interpreta la orden que recibe una puerta.

    Un mensaje invalido se ignora (None). Un hold_ms invalido NO invalida
    la orden: se descarta y la puerta usa su valor por defecto, porque
    abrir una puerta es mas importante que respetar un seguro mal escrito.
    """
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None

    if not isinstance(data, dict):
        return None

    action = data.get(FIELD_ACTION)

    if not isinstance(action, str) or action.strip().lower() not in VALID_DOOR_ACTIONS:
        return None

    hold_ms = data.get(FIELD_HOLD_MS)

    # bool es subclase de int en Python; se descarta explicitamente
    if not isinstance(hold_ms, int) or isinstance(hold_ms, bool) or hold_ms <= 0:
        hold_ms = None

    return DoorCommand(action=action.strip().lower(), hold_ms=hold_ms)
