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
from pathlib import Path

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

# ─── Direccion del panel de administracion ─────────────────────────────────────
ADMIN_PANEL_DIR = Path(__file__).resolve().parents[2] / "frontend"

# ─── Constantes para la clave de desarrollador ─────────────────────────────────────
DEV_KEY_HEADER_NAME = "X-Dev-Key"
DEV_KEY_FILE_PATH = Path(__file__).resolve().parents[1] / "data" / "dev_access_key.txt"
DEV_KEY_BYTES = 24

# ─── Dispositivos (luces y puertas) ─────────────────────────────────────
DEVICE_TYPE_LIGHT: str = "light" # Luz de una habitacion (una unidad que se controla)
DEVICE_TYPE_DOOR: str = "door" # Puerta de una habitacion
VALID_DEVICE_TYPES: tuple = (DEVICE_TYPE_LIGHT, DEVICE_TYPE_DOOR)
DEVICE_KEY_PATTERN: str = r"^[a-z0-9_]+$" # Solo minusculas, numeros y guion bajo (TENERLO EN CUENTA PARA EL MQTT)
DEVICE_KEY_MAX_LENGTH: int = 50