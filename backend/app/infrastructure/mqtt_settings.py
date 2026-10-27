"""
app/infrastructure/mqtt_settings.py

Ajustes de conexion al broker MQTT.

Responsabilidad: Reunir en un solo objeto los datos para conectarse
(direccion, usuario, clave...). La clave NUNCA vive en el codigo:
se lee de la variable de entorno INCLUSIVE_MQTT_PASSWORD o, si no
existe, del archivo data/mqtt_password.txt (que no se sube al repositorio).
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
    """
    Busca la clave primero en la variable de entorno y luego en el archivo.

    Returns:
        La clave, o texto vacio si no se encontro (el broker la rechazara
        y el error quedara en el log).
    """
    from_env = os.getenv(config.MQTT_PASSWORD_ENV_NAME)

    if from_env is not None:
        return from_env.strip()

    password_file = config.MQTT_PASSWORD_FILE_PATH

    if password_file.exists():
        return password_file.read_text(encoding="utf-8").strip()

    return ""


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
