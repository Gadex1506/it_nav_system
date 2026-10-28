"""
app/infrastructure/mqtt_settings.py

Ajustes de conexion al broker MQTT.

Responsabilidad: Reunir en un solo objeto los datos para conectarse
(direccion, usuario, clave...). La clave NUNCA vive en el codigo:
se lee de la variable de entorno INCLUSIVE_MQTT_PASSWORD.
"""

import os
from dataclasses import dataclass

from app import config


@dataclass(frozen=True)
class MqttSettings:
    """Datos necesarios para conectarse al broker."""

    host: str
    port: int
    username: str
    password: str
    client_id: str
    keepalive_seconds: int
    qos: int
    reconnect_min_seconds: int
    reconnect_max_seconds: int


def _read_password() -> str:
    """Lee la clave del broker desde la variable de entorno (cargada del .env)."""
    return os.getenv(config.MQTT_PASSWORD_ENV_NAME, "").strip()


def load_mqtt_settings() -> MqttSettings:
    """Construye los ajustes con los valores actuales de config."""
    return MqttSettings(
        host=config.MQTT_HOST,
        port=config.MQTT_PORT,
        username=config.MQTT_USERNAME,
        password=_read_password(),
        client_id=config.MQTT_CLIENT_ID,
        keepalive_seconds=config.MQTT_KEEPALIVE_SECONDS,
        qos=config.MQTT_QOS,
        reconnect_min_seconds=config.MQTT_RECONNECT_MIN_SECONDS,
        reconnect_max_seconds=config.MQTT_RECONNECT_MAX_SECONDS,
    )
