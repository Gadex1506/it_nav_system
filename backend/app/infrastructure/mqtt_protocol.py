"""
app/infrastructure/mqtt_protocol.py

Traductor entre el contrato MQTT y los objetos del dominio.

Responsabilidad: Es el UNICO archivo que conoce los nombres de los
temas y la forma de los mensajes del contrato. Si el contrato cambia
(un nombre de tema, un campo), solo se edita este archivo.

Son funciones puras: no abren conexiones ni guardan estado, por eso
se prueban facilmente sin un broker.

Patron aplicado:
    - Adapter (parte "traductor"): convierte el idioma del contrato
    (temas y JSON) al idioma interno (DeviceStateReport, etc.).
"""

import json
import logging
import re
from typing import Optional

from app import config
from app.domain.device_events import (
    BoardAvailabilityReport,
    DeviceAvailabilityReport,
    DeviceStateReport,
)

logger = logging.getLogger(__name__)

# Piezas de los temas, tal como estan en el contrato
DEVICES_SEGMENT = "devices"
BOARDS_SEGMENT = "boards"
TOPIC_SET = "set"
TOPIC_STATE = "state"
TOPIC_AVAILABILITY = "availability"
SINGLE_LEVEL_WILDCARD = "+"

# Campos del JSON del contrato
FIELD_STATE = "state"
FIELD_ACTION = "action"
FIELD_HOLD_MS = "hold_ms"
FIELD_TIMESTAMP = "ts_ms"

_DEVICE_KEY_REGEX = re.compile(config.DEVICE_KEY_PATTERN)
_DEVICE_TOPIC_PARTS = 2  # {device_key}/{tipo_de_tema}
_BOARD_TOPIC_PARTS = 2   # {board_id}/{tipo_de_tema}


def _devices_prefix() -> str:
    """Prefijo comun de todos los temas de dispositivos fijos."""
    return f"{config.MQTT_TOPIC_ROOT}/{DEVICES_SEGMENT}"


def _boards_prefix() -> str:
    """Prefijo comun de los temas de las placas ESP32."""
    return f"{config.MQTT_TOPIC_ROOT}/{BOARDS_SEGMENT}"


# ─── Temas que el backend publica ────────────────────────────────────────

def device_set_topic(device_key: str) -> str:
    """Tema donde se le da una orden a un dispositivo (luz o puerta)."""
    return f"{_devices_prefix()}/{device_key}/{TOPIC_SET}"


def light_set_topic(device_key: str) -> str:
    """Tema donde se pide encender o apagar una luz."""
    return device_set_topic(device_key)


def door_set_topic(device_key: str) -> str:
    """Tema donde se pide abrir o cerrar una puerta."""
    return device_set_topic(device_key)


# ─── Temas a los que el backend se suscribe ──────────────────────────────

def state_subscription_topic() -> str:
    """Filtro que recibe el estado de TODOS los dispositivos."""
    return f"{_devices_prefix()}/{SINGLE_LEVEL_WILDCARD}/{TOPIC_STATE}"


def availability_subscription_topic() -> str:
    """Filtro que recibe online/offline de TODOS los dispositivos."""
    return f"{_devices_prefix()}/{SINGLE_LEVEL_WILDCARD}/{TOPIC_AVAILABILITY}"


def board_availability_subscription_topic() -> str:
    """Filtro que recibe online/offline de TODAS las placas (contrato v0.3)."""
    return f"{_boards_prefix()}/{SINGLE_LEVEL_WILDCARD}/{TOPIC_AVAILABILITY}"


def parse_board_topic(topic: str) -> Optional[tuple[str, str]]:
    """
    Separa un tema de placa en (board_id, tipo_de_tema).

    Ejemplo:
        'inclusive/casa1/boards/casa/availability' -> ('casa', 'availability')

    Returns:
        La pareja, o None si el tema no es de una placa o esta mal formado.
    """
    prefix = _boards_prefix() + "/"

    if not topic.startswith(prefix):
        return None

    parts = topic[len(prefix):].split("/")

    if len(parts) != _BOARD_TOPIC_PARTS:
        return None

    board_id, topic_kind = parts

    if not _DEVICE_KEY_REGEX.match(board_id):
        return None

    return board_id, topic_kind


def parse_device_topic(topic: str) -> Optional[tuple[str, str]]:
    """
    Separa un tema de dispositivo en (device_key, tipo_de_tema).

    Ejemplo:
        'inclusive/casa1/devices/light_sala/state' -> ('light_sala', 'state')

    Returns:
        La pareja, o None si el tema no tiene la forma esperada
        (otra raiz, niveles de mas, device_key invalido).
    """
    prefix = _devices_prefix() + "/"

    if not topic.startswith(prefix):
        return None

    parts = topic[len(prefix):].split("/")

    if len(parts) != _DEVICE_TOPIC_PARTS:
        return None

    device_key, topic_kind = parts

    if not _DEVICE_KEY_REGEX.match(device_key):
        return None

    return device_key, topic_kind


# ─── Mensajes ────────────────────────────────────────────────────────────

def encode_light_command(state: str) -> bytes:
    """
    Construye el JSON de la orden para una luz: {"state":"on"}.

    Returns:
        El mensaje en UTF-8 y sin espacios sobrantes.
    """
    return json.dumps({FIELD_STATE: state}, separators=(",", ":")).encode("utf-8")


def encode_door_command(action: str, hold_ms: Optional[int] = None) -> bytes:
    """
    Construye el JSON de la orden para una puerta.

    Ejemplos:
        {"action":"open","hold_ms":10000}   |   {"action":"close"}

    El campo hold_ms solo viaja si se indico: si falta, el ESP32 usa su
    valor por defecto (contrato).
    """
    payload: dict = {FIELD_ACTION: action}

    if hold_ms is not None:
        payload[FIELD_HOLD_MS] = hold_ms

    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def decode_state_payload(device_key: str, payload: bytes) -> Optional[DeviceStateReport]:
    """
    Convierte el JSON de estado que publica un ESP32 en un reporte.

    Un mensaje mal formado NO debe tumbar al backend: se registra un
    aviso y se devuelve None para ignorarlo.

    Returns:
        El reporte, o None si el mensaje es invalido.
    """
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("Estado ignorado de '%s': no es JSON valido.", device_key)
        return None

    state = data.get(FIELD_STATE) if isinstance(data, dict) else None

    if not isinstance(state, str) or not state.strip():
        logger.warning("Estado ignorado de '%s': falta el campo 'state'.", device_key)
        return None

    timestamp = data.get(FIELD_TIMESTAMP)
    # bool es subclase de int en Python; se descarta explicitamente
    if not isinstance(timestamp, int) or isinstance(timestamp, bool):
        timestamp = None

    return DeviceStateReport(
        device_key=device_key,
        state=state.strip().lower(),
        timestamp_ms=timestamp,
    )


def _parse_online_text(source: str, payload: bytes) -> Optional[bool]:
    """
    Interpreta el texto 'online'/'offline' (comun a dispositivos y placas).

    Returns:
        True/False, o None (con aviso en el log) si el texto no es valido.
    """
    try:
        text = payload.decode("utf-8").strip().lower()
    except UnicodeDecodeError:
        logger.warning("Disponibilidad ignorada de '%s': texto ilegible.", source)
        return None

    if text == config.AVAILABILITY_ONLINE:
        return True

    if text == config.AVAILABILITY_OFFLINE:
        return False

    logger.warning("Disponibilidad ignorada de '%s': valor '%s'.", source, text)
    return None


def decode_availability_payload(
    device_key: str, payload: bytes
) -> Optional[DeviceAvailabilityReport]:
    """Convierte 'online'/'offline' de un dispositivo en un reporte (o None si es invalido)."""
    online = _parse_online_text(device_key, payload)
    return None if online is None else DeviceAvailabilityReport(device_key=device_key, online=online)


def decode_board_availability_payload(
    board_id: str, payload: bytes
) -> Optional[BoardAvailabilityReport]:
    """Convierte 'online'/'offline' de una placa en un reporte (o None si es invalido)."""
    online = _parse_online_text(board_id, payload)
    return None if online is None else BoardAvailabilityReport(board_id=board_id, online=online)