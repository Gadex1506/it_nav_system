"""
config.py

Modulo de configuracion central del sistema de navegacion de InclusiveTech.

Responsabilidad: Centralizar todas las constantes y parametros
configurables del sistema en un unico lugar, evitando cadenas 
dispersas en el codigo.

Principio SOLID aplicado:
    O (Open/Closed): Los valores se cambian aqui sin modificar
    ningun otro modulo del sistema.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Carga el archivo .env (busca hacia arriba desde esta carpeta). Si una
# variable ya existe en el sistema, esa gana sobre la del .env.
load_dotenv()

# ─── Asistente de voz ────────────────────────────────────────────
ASSISTANT_NAME: str = "Mia"

# ─── Base de datos ───────────────────────────────────────────────
DATABASE_NAME: str = "inclusivetech_navigation.db"
DATABASE_PATH: str = f"data/{DATABASE_NAME}"

# ─── Tipos de nodo validos ───────────────────────────────────────
NODE_TYPE_ROOM: str = "room" # Habitacion con nombre visible
NODE_TYPE_WAYPOINT: str = "waypoint" # Punto intermedio de navegacion
VALID_NODE_TYPES: tuple = (NODE_TYPE_ROOM, NODE_TYPE_WAYPOINT)

# ─── Configuracion para los alias ───────────────────────────────────────
MAX_ALIASES_PER_NODE: int = 5 # Se puede modificar la cantidad de alias por nodo

# ─── Roles de acceso (para separar endpoints dev vs usuario) ─────
ROLE_DEVELOPER: str = "developer"
ROLE_USER: str = "user"

# ─── Estado de nodos ─────────────────────────────────────────────
NODE_STATUS_ACTIVE: str = "active"
NODE_STATUS_INACTIVE: str = "inactive"

# ─── Servidor HTTP ─────────────────────────────────────────────────────
# Por defecto escucha SOLO en este equipo: los endpoints de usuario no piden clave.
# Para exponerlo en la red (no recomendado) define INCLUSIVE_API_HOST=0.0.0.0 en el .env.
API_HOST: str = os.getenv("INCLUSIVE_API_HOST", "127.0.0.1")
API_PORT: int = 8001

# ─── Direccion del panel de administracion ─────────────────────────────────────
ADMIN_PANEL_DIR = Path(__file__).resolve().parents[2] / "frontend"

# ─── Constantes para la clave de desarrollador ─────────────────────────────────────
DEV_KEY_HEADER_NAME = "X-Dev-Key"
DEV_KEY_ENV_NAME = "INCLUSIVE_DEV_KEY"       # Nombre de la variable en el .env
DEV_KEY_MIN_LENGTH = 16                      # Una clave mas corta se considera debil
DEV_ACCESS_KEY: str = os.getenv(DEV_KEY_ENV_NAME, "").strip()

# ─── Dispositivos (luces y puertas) ─────────────────────────────────────
DEVICE_TYPE_LIGHT: str = "light" # Luz de una habitacion (una unidad que se controla)
DEVICE_TYPE_DOOR: str = "door" # Puerta de una habitacion
VALID_DEVICE_TYPES: tuple = (DEVICE_TYPE_LIGHT, DEVICE_TYPE_DOOR)
DEVICE_KEY_PATTERN: str = r"^[a-z0-9_]+$" # Solo minusculas, numeros y guion bajo (TENERLO EN CUENTA PARA EL MQTT)
DEVICE_KEY_MAX_LENGTH: int = 50

# ────────────────────────────────── MQTT ────────────────────────────────── 

# ─── Luces: estados validos (igual que el contrato MQTT) ─────────────────
LIGHT_STATE_ON: str = "on"
LIGHT_STATE_OFF: str = "off"
VALID_LIGHT_STATES: tuple = (LIGHT_STATE_ON, LIGHT_STATE_OFF)

# ─── Puertas: acciones validas (igual que el contrato MQTT) ──────────────
DOOR_ACTION_OPEN: str = "open"
DOOR_ACTION_CLOSE: str = "close"
VALID_DOOR_ACTIONS: tuple = (DOOR_ACTION_OPEN, DOOR_ACTION_CLOSE)
DOOR_HOLD_MS_MIN: int = 1000   # hold_ms = cierre de seguridad; menos de 1 s es casi seguro un error de tipeo
DOOR_HOLD_MS_MAX: int = 60000  # mas de 1 minuto abierta ya no es "seguro", es un olvido

# ─── Seguimiento de ordenes: cuanto esperar el estado de vuelta (contrato v0.3) ──
ORDER_TIMEOUT_LIGHT_SECONDS: float = 3.0    # Luz: si no llega el estado nuevo, "no respondio"
ORDER_TIMEOUT_DOOR_SECONDS: float = 10.0    # Puerta (por confirmar con el hardware real)
ORDER_PROBLEM_VISIBLE_SECONDS: float = 60.0 # Un problema solo se muestra este tiempo; despues se considera viejo
# Estados de puerta (igual que el contrato MQTT)
DOOR_STATE_CLOSED: str = "closed"
DOOR_STATE_OPENING: str = "opening"
DOOR_STATE_OPEN: str = "open"
DOOR_STATE_CLOSING: str = "closing"
DOOR_STATE_BLOCKED: str = "blocked"

# Que estados confirman cada orden de puerta (el primero que llegue basta)
DOOR_CONFIRMING_STATES: dict = {
    DOOR_ACTION_OPEN: (DOOR_STATE_OPENING, DOOR_STATE_OPEN),
    DOOR_ACTION_CLOSE: (DOOR_STATE_CLOSING, DOOR_STATE_CLOSED),
}
DOOR_FAILURE_STATES: tuple = (DOOR_STATE_BLOCKED,)  # Estados que significan "no pudo hacerlo"

# ─── Disponibilidad de dispositivos (Last Will de MQTT) ──────────────────
AVAILABILITY_ONLINE: str = "online"
AVAILABILITY_OFFLINE: str = "offline"

# ─── MQTT: pasarela hacia los ESP32 ──────────────────────────────────────
# Los valores sensibles o que cambian de equipo en equipo se leen de
# variables de entorno; si no existen se usan estos valores por defecto.
MQTT_ENABLED: bool = os.getenv("INCLUSIVE_MQTT_ENABLED", "true").lower() == "true"
MQTT_HOST: str = os.getenv("INCLUSIVE_MQTT_HOST", "localhost")
MQTT_PORT: int = int(os.getenv("INCLUSIVE_MQTT_PORT", "1883"))
MQTT_USERNAME: str = os.getenv("INCLUSIVE_MQTT_USER", "inclusive_backend")
MQTT_PASSWORD_ENV_NAME: str = "INCLUSIVE_MQTT_PASSWORD"
MQTT_CLIENT_ID: str = "inclusive-backend"
MQTT_TOPIC_ROOT: str = "inclusive/casa1" # Raiz fija del contrato
MQTT_HOUSE_BOARD_ID: str = "casa"        # Placa ESP32 que maneja las luces y puertas (contrato v0.3)
MQTT_QOS: int = 1 # Ordenes y estados: al menos una vez
MQTT_KEEPALIVE_SECONDS: int = 30
MQTT_RECONNECT_MIN_SECONDS: int = 1
MQTT_RECONNECT_MAX_SECONDS: int = 30