-- schema.sql
-- ============================================================
-- Schema de base de datos para el sistema SmartHome con ARIA.
--
-- Responsabilidad: Definir la estructura relacional completa
-- que soporta el grafo de navegación, el soporte multi-casa
-- y el sistema de alias de voz para el asistente.
--
-- Patrón aplicado: Repository Pattern (este schema es la base
-- sobre la cual el repositorio abstrae todo acceso a datos).
-- ============================================================

PRAGMA foreign_keys = ON;

-- ─── Tabla: houses ──────────────────────────────────────────────
-- Representa una instalacion domotica completa.
-- Permite soportar multiples casas en la misma base de datos.
CREATE TABLE IF NOT EXISTS houses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, -- "Casa de prueba 1"
    description TEXT, -- Descripcion opcional
    created_at DATETIME DEFAULT(datetime('now')),
    updated_at DATETIME DEFAULT(datetime('now'))
);

-- ─── Tabla: nodes ───────────────────────────────────────────────
-- Representa cada nodo del grafo de navegacion.
-- Un nodo puede ser una habitacion (room) o un punto intermedio
-- de navegacion (waypoint). Ambos tipos comparten esta tabla.
CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    house_id INTEGER NOT NULL,
    node_type TEXT NOT NULL DEFAULT 'room', -- 'room' | 'waypoint'
    internal_name TEXT NOT NULL, -- Nombre tecnico, inmutable
    display_name TEXT NOT NULL, -- Nombre visible al usuario

    -- Posicion del NODO en Unity registrada automaticamente desde el Editor en Unity
    unity_pos_x REAL NOT NULL DEFAULT 0.0, 
    unity_pos_y REAL NOT NULL DEFAULT 0.0, 
    unity_pos_z REAL NOT NULL DEFAULT 0.0, 

    -- Posicion fisica en la maqueta. Son editables desde el panel web
    physical_pos_x  REAL,
    physical_pos_y  REAL,

    -- Metadatos
    status TEXT NOT NULL DEFAULT 'active', -- 'active' | 'inactive'
    created_at DATETIME DEFAULT(datetime('now')),
    updated_at DATETIME DEFAULT(datetime('now'))
);

-- ─── Tabla: node_aliases ────────────────────────────────────────
-- Alias de voz que ARIA reconoce para referirse a un nodo.
-- Un node puede tener multiples alias. Seperado de nodes para
-- cumplir la primera forma normal y facilitar busquedas por voz.
-- Ejemplo: nodo "Sala Principal" -> aliases "sala", "living"
CREATE TABLE IF NOT EXISTS node_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id INTEGER NOT NULL,
    alias TEXT NOT NULL,
    created_at DATETIME DEFAULT(datetime('now')),
    
    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE,
    UNIQUE (node_id, alias) -- Un alias no se repite en el mismo nodo
);

-- ─── Tabla: node_edges (aristas) ──────────────────────────────────────────
-- Aristas del grafo de navegacion entre nodos.
-- Representa las conexiones bidireccionales o unidireccionales
-- entre nodos que el agente puede recorrer.
CREATE TABLE IF NOT EXISTS node_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_node_id INTEGER NOT NULL,
    to_node_id INTEGER NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0, -- Costo de la arista (para pathfinding)
    is_bidirectional BOOLEAN NOT NULL DEFAULT 1, -- 1 = va y vuelve, 0 = solo ida
    created_at DATETIME DEFAULT(datetime('now')),

    FOREIGN KEY (from_node_id) REFERENCES nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (to_node_id) REFERENCES nodes(id) ON DELETE CASCADE,
    UNIQUE (from_node_id, to_node_id) -- No duplicar aristas
);

-- ─── Tabla: devices ─────────────────────────────────────────────
-- Dispositivos controlables de una habitacion (luces y puertas).
-- Un registro es una UNIDAD QUE SE CONTROLA, no una bombilla. La luz de
-- la sala puede ser una lampara o cuatro y sigue siendo un dispositivo 
-- (como si lo que se registrara fuera un interrumptor).
-- El estado (encendido/abierto) NO se guarda aqui, lo reporta el dispositivo.
-- device_key es el identificador fijo del contrato MQTT (ej: 'light_living').
-- Al borrar el nodo se borran sus dispositivos (y al borrar la casa, sus nodos).
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id INTEGER NOT NULL,
    device_type TEXT NOT NULL CHECK (device_type IN ('light', 'door')), -- Debe coincidir con VALID_DEVICE_TYPES
    device_key TEXT NOT NULL UNIQUE, -- Identificador tecnico fijo
    display_name TEXT NOT NULL, -- Nombre visible, editable
    created_at DATETIME DEFAULT(datetime('now')),
    updated_at DATETIME DEFAULT(datetime('now')),

    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
);

-- ─── Indices para optimizar consultas frecuentes ─────────────────
CREATE INDEX IF NOT EXISTS idx_nodes_house_id
    ON nodes(house_id);

CREATE INDEX IF NOT EXISTS idx_nodes_status
    ON nodes(status);

CREATE INDEX IF NOT EXISTS idx_node_aliases_node_id
    ON node_aliases(node_id);

CREATE INDEX IF NOT EXISTS idx_node_aliases_alias
    ON node_aliases(alias);

CREATE INDEX IF NOT EXISTS idx_node_edges_from
    ON node_edges(from_node_id);

CREATE INDEX IF NOT EXISTS idx_devices_node_id
    ON devices(node_id);

CREATE INDEX IF NOT EXISTS idx_devices_type
    ON devices(device_type);