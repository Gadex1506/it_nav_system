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
from app.domain.device_events import DeviceAvailabilityReport, DeviceStateReport

logger = logging.getLogger(__name__)

# Piezas de los temas, tal como estan en el contrato
DEVICES_SEGMENT = "devices"
TOPIC_SET = "set"
TOPIC_STATE = "state"
TOPIC_AVAILABILITY = "availability"
SINGLE_LEVEL_WILDCARD = "+"

# Campos del JSON del contrato
FIELD_STATE = "state"
FIELD_TIMESTAMP = "ts_ms"

_DEVICE_KEY_REGEX = re.compile(config.DEVICE_KEY_PATTERN)
_DEVICE_TOPIC_PARTS = 2  # {device_key}/{tipo_de_tema}


def _devices_prefix() -> str:
    """Prefijo comun de todos los temas de dispositivos fijos."""
    return f"{config.MQTT_TOPIC_ROOT}/{DEVICES_SEGMENT}"


# ─── Temas que el backend publica ────────────────────────────────────────

def light_set_topic(device_key: str) -> str:
    """Tema donde se pide encender o apagar una luz."""
    return f"{_devices_prefix()}/{device_key}/{TOPIC_SET}"


# ─── Temas a los que el backend se suscribe ──────────────────────────────

def state_subscription_topic() -> str:
    """Filtro que recibe el estado de TODOS los dispositivos."""
    return f"{_devices_prefix()}/{SINGLE_LEVEL_WILDCARD}/{TOPIC_STATE}"


def availability_subscription_topic() -> str:
    """Filtro que recibe online/offline de TODOS los dispositivos."""
    return f"{_devices_prefix()}/{SINGLE_LEVEL_WILDCARD}/{TOPIC_AVAILABILITY}"


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


def decode_availability_payload(
    device_key: str, payload: bytes
) -> Optional[DeviceAvailabilityReport]:
    """
    Convierte el texto 'online' u 'offline' en un reporte de conexion.

    Returns:
        El reporte, o None si el texto no es ninguno de los dos.
    """
    try:
        text = payload.decode("utf-8").strip().lower()
    except UnicodeDecodeError:
        logger.warning("Disponibilidad ignorada de '%s': texto ilegible.", device_key)
        return None

    if text == config.AVAILABILITY_ONLINE:
        return DeviceAvailabilityReport(device_key=device_key, online=True)

    if text == config.AVAILABILITY_OFFLINE:
        return DeviceAvailabilityReport(device_key=device_key, online=False)

    logger.warning("Disponibilidad ignorada de '%s': valor '%s'.", device_key, text)
    return None
