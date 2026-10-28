"""
simulator/settings.py

Valores por defecto y ajustes de conexion del simulador.

La contrasena NUNCA va en el codigo: se lee de la variable
INCLUSIVE_ESP32_PASSWORD, que normalmente vive en el archivo .env
(el mismo que usa el backend, fuera del repositorio).
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Busca el .env hacia arriba desde esta carpeta; lo ya definido en el sistema gana
load_dotenv()

DEFAULT_MQTT_HOST = "localhost"
DEFAULT_MQTT_PORT = 1883
DEFAULT_MQTT_USER = "inclusive_esp32"   # Mismo usuario que usaran los ESP32 reales
DEFAULT_BACKEND_URL = "http://localhost:8001"
DEFAULT_HOUSE_ID = 1
DEFAULT_LATENCY_MS = 300                # Lo que tarda "el hardware" en reaccionar
DEFAULT_DOOR_TRAVEL_MS = 1500           # Lo que tarda el servo en abrir o cerrar (por confirmar con hardware)
DEFAULT_DOOR_HOLD_MS = 10000            # Cierre de seguridad si la orden no trae hold_ms (por confirmar)

KEEPALIVE_SECONDS = 30
RECONNECT_MIN_SECONDS = 1
RECONNECT_MAX_SECONDS = 10
HTTP_TIMEOUT_SECONDS = 5
MS_PER_SECOND = 1000
GRACEFUL_STOP_WAIT_SECONDS = 2

PASSWORD_ENV_NAME = "INCLUSIVE_ESP32_PASSWORD"


@dataclass(frozen=True)
class SimulatorSettings:
    """Datos de conexion de los dispositivos simulados."""

    host: str
    port: int
    username: str
    password: str
    latency_seconds: float


def read_password() -> str:
    """
    Lee la contrasena del ESP32 desde la variable de entorno (cargada del .env).

    Returns:
        La contrasena, o texto vacio si no existe (el broker la rechazara
        y el error quedara en el log).
    """
    return os.getenv(PASSWORD_ENV_NAME, "").strip()
