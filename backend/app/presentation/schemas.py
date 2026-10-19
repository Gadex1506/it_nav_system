"""
app/presentation/schemas.py

Schemas Pydantic para validación de requests y responses HTTP.

Responsabilidad: Definir la estructura exacta de los datos que
entran y salen de la API. Actuan como DTOs (Data Transfer Objects)
entre el mundo HTTP y el dominio interno del sistema.

Patron aplicado:
    - DTO (Data Transfer Object): Cada schema transporta datos
    entre capas sin contener logica de negocio.

Principios SOLID aplicados:
    - S: Cada schema tiene una unica responsabilidad de validacion.
    - I: Schemas especificos para cada operacion, no uno general
    que sirva para todo.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional
from app.config import (
    NODE_TYPE_ROOM,
    NODE_TYPE_WAYPOINT,
    VALID_NODE_TYPES,
    VALID_DEVICE_TYPES,
    DEVICE_KEY_PATTERN,
    DEVICE_KEY_MAX_LENGTH,
)


# ==================================================================
# SCHEMAS DE HOUSE
# ==================================================================

class HouseCreateRequest(BaseModel):
    """
    Schema para crear una nueva casa.
    
    SOLO EL DESARROLLADOR USA ESTE SCHEMA (endpoint /dev)
    """

    name: str = Field(
        min_length=1,
        max_length=100,
        description="Nombre descriptivo de la casa"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=300,
        description="Descripcion opcional de la instalacion"
    )

class HouseResponse(BaseModel):
    """
    Schema de respuesta para una casa.
    
    Define exactamente que campos del dominio se exponen al anterior.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class HouseSummaryResponse(HouseResponse):
    """Casa con datos extra para el panel de desarrollo."""
    node_count: int = Field(description="Cantidad de nodos que tiene la casa")
    is_active: bool = Field(description="True si es la casa activa (ACTIVE_HOUSE_ID)")


class HousesOverviewResponse(BaseModel):
    """Resumen de casas. active_house_id es None si no hay ninguna."""

    active_house_id: Optional[int] = None
    houses: list[HouseSummaryResponse]

# ==================================================================
# SCHEMAS DE POSICION
# ==================================================================

class UnityPositionSchema(BaseModel):
    """Schema para la posicion 3D de un nodo en Unity."""
    x: float = Field(default=0.0, description="Coordenada X en Unity")
    y: float = Field(default=0.0, description="Coordenada Y en Unity")
    z: float = Field(default=0.0, description="Coordenada Z en Unity")


class PhysicalPositionSchema(BaseModel):
    """Schema para la posicion 2D de un nodo en la maqueta."""
    x: float = Field(default=0.0, description="Coordenada X en la maqueta")
    y: float = Field(default=0.0, description="Coordenada Y en la maqueta")


# ==================================================================
# SCHEMAS DE NODE ALIAS
# ==================================================================

class AliasCreateRequest(BaseModel):
    """Schema para agregar un alias de voz a un nodo."""
    alias: str = Field(
        min_length=1,
        max_length=50,
        description="Alias de voz que MIA reconocera"
    )

    @field_validator("alias")
    @classmethod
    def normalize_alias(cls, value: str) -> str:
        """
        Normaliza el alias a minusculas y sin espacios extras.
        Garantiza consistencia en las busquedas de voz de MIA.
        """
        return value.strip().lower()

class AliasResponse(BaseModel):
    """Schema de respuesta para un alias de voz."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    node_id: int
    alias: str
    created_at: Optional[str] = None


# ==================================================================
# SCHEMAS DE NODE
# ==================================================================

class NodeCreateRequest(BaseModel):
    """
    Schema para crear un nuevo nodo desde Unity (endpoint /dev).

    SOLO EL DESARROLLADOR USA ESTE SCHEMA. Incluye todos los
    campos necesarios para registrar un nodo completo desde
    el Editor de Unity.
    """

    house_id: int = Field(description="ID de la casa propietaria")

    node_type: str = Field(
        description=f"Tipo de nodo: '{NODE_TYPE_ROOM}' o '{NODE_TYPE_WAYPOINT}'"
    )

    internal_name: str = Field(
        min_length=1,
        max_length=100,
        description="Nombre tecnico unico e inmutable para un nodo"
    )

    display_name: str = Field(
        min_length=1,
        max_length=100,
        description="Nombre del nodo visible para el usuario"
    )

    unity_x: float = Field(default=0.0, description="Posicion X del nodo en Unity")
    unity_y: float = Field(default=0.0, description="Posicion Y del nodo en Unity")
    unity_z: float = Field(default=0.0, description="Posicion Z del nodo en Unity")

    physical_x: Optional[float] = Field(
        default=None,
        description="Posicion X del nodo en la maqueta"
    )

    physical_y: Optional[float] = Field(
        default=None,
        description="Posicion Y del nodo en la maqueta"
    )

    @field_validator("node_type")
    @classmethod
    def validate_node_type(cls, value: str) -> str:
        """Valida que el tipo de nodo sea uno de los valores permitidos."""
        if value not in VALID_NODE_TYPES:
            raise ValueError(
                f"Tipo de nodo invalido: {value}"
                f"Valores permitidos: {VALID_NODE_TYPES}"
            )
        return value
    
    @field_validator("internal_name")
    @classmethod
    def normalize_internal_name(cls, value: str) -> str:
        """Normaliza el nombre interno a mayusculas sin espacios extras."""
        return value.strip().upper()


class NodeUpdateDisplayNameRequest(BaseModel):
    """
    Schema para que el usuario actualice el nombre visible de un nodo.
    
    Es intencionalmente minimalista: El usuario SOLO puede cambiar
    el display_name. Nada mas. Esto protege la integridad del sistema.
    """

    display_name: str = Field(
        min_length=1,
        max_length=100,
        description="Nuevo nombre visible para el nodo"
    )


class NodeUpdatePhysicalPositionRequest(BaseModel):
    """Schema para actualizar la posicion fisica de un nodo en la maqueta."""
    x: float = Field(description="Nueva coordenada X del nodo en la maqueta")
    y: float = Field(description="Nueva coordenada Y del nodo en la maqueta")


class NodeResponse(BaseModel):
    """
    Schema de respuesta completo para un nodo.

    Incluye sus alias y posiciones. No expone campos internos
    como el status o timestamps de infraestructura innecesarios
    para el usuario o consumidor.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    node_type: str
    internal_name: str
    display_name: str
    unity_position: UnityPositionSchema
    physical_position: Optional[PhysicalPositionSchema] = None
    status: str
    aliases: list[AliasResponse] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ==================================================================
# SCHEMAS DE NODE EDGE
# ==================================================================

class EdgeCreateRequest(BaseModel):
    """Schema para crear una arista entre dos nodos (endpoint /dev)."""

    from_node_id: int = Field(description="ID del nodo de origen")
    to_node_id: int = Field(description="ID del nodo de destino")

    weight: float = Field(
        default=1.0,
        gt=0,
        description="Costo de la arista. Debe ser mayor a 0"
    )

    is_bidirectional: bool = Field(
        default=True,
        description="True si la conexion es de ida y de vuelta"
    )

class EdgeResponse(BaseModel):
    """Schema de respuesta para una arista del grafo."""

    model_config = ConfigDict(from_attributes=True)

    id:int
    from_node_id: int
    to_node_id: int
    weight: float
    is_bidirectional: bool
    created_at: Optional[str] = None

# ==================================================================
# SCHEMAS DE DEVICE (luces y puertas)
# ==================================================================

class DeviceCreateRequest(BaseModel):
    """
    Schema para registrar un dispositivo en una habitacion (endpoint /dev).

    Un dispositivo es una unidad que se controla: la luz de la sala es
    UN dispositivo aunque tenga varias lamparas.
    """

    node_id: int = Field(description="ID del nodo (habitacion) donde se instala")

    device_type: str = Field(
        description=f"Tipo de dispositivo. Valores: {VALID_DEVICE_TYPES}"
    )

    device_key: str = Field(
        min_length=1,
        max_length=DEVICE_KEY_MAX_LENGTH,
        pattern=DEVICE_KEY_PATTERN,
        description="Identificador fijo del contrato MQTT. Ej: light_living"
    )

    display_name: str = Field(
        min_length=1,
        max_length=100,
        description="Nombre visible del dispositivo. Ej: Luz de la sala"
    )

    @field_validator("device_type")
    @classmethod
    def validate_device_type(cls, value: str) -> str:
        """Valida que el tipo de dispositivo sea uno de los permitidos."""
        if value not in VALID_DEVICE_TYPES:
            raise ValueError(
                f"Tipo de dispositivo invalido: {value}. "
                f"Valores permitidos: {VALID_DEVICE_TYPES}"
            )
        return value


class DeviceUpdateDisplayNameRequest(BaseModel):
    """Schema para cambiar el nombre visible de un dispositivo."""

    display_name: str = Field(
        min_length=1,
        max_length=100,
        description="Nuevo nombre visible del dispositivo"
    )


class DeviceResponse(BaseModel):
    """Schema de respuesta para un dispositivo."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    node_id: int
    device_type: str
    device_key: str
    display_name: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

# ==================================================================
# SCHEMA GENERICO DE RESPUESTA
# ==================================================================

class MessageResponse(BaseModel):
    """
    Schema generico para respuestas de operaciones simples.
    Usado en operaciones de eliminacion o confirmaciones.
    """
    success: bool
    message: str