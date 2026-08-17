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

# ─── Asistente de voz ────────────────────────────────────────────
ASSISTANT_NAME: str = "NOVA"

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

# ─── Casa activa del sistema ─────────────────────────────────────
# ID de la casa configurada en esta instalación domótica.
ACTIVE_HOUSE_ID: int = 1