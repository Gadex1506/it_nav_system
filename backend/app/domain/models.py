"""
# app/domain/models.py

Modelos de dominio del sistema de navegacion.

Responsabilidad: Definir las entidades del dominio y sus Value
Objects. Estas clases representan el nucleo del negocio y son
completamente independientes de la base de datos, el framework
web o cualquier infraestructura externa.

Patrones aplicados:
    - Value Object: UnityPosition y PhysicalPosition son
    inmutables y se comparan por valor, no por identidad.
    - Factory Method: Metodos de clase que centralizan la creacion
    de entidades garantizando su validez desde el inicio.

Principios SOLID aplicados:
    - S: Cada clase tiene una unica responsabilidad.
    - O: Nuevos tipos de nodo se agregan extendiendo, no modificando.
    - D: Sin dependencias de infraestructura externa.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.config import (
    NODE_TYPE_ROOM,
    NODE_TYPE_WAYPOINT,
    NODE_STATUS_ACTIVE,
    VALID_NODE_TYPES,
)

# =============================================================
# VALUE OBJECTS
# Clases inmutables que se comparan por valor, no por identidad.
# No tienen un ID propio porque no son entidades independientes.
# =============================================================

@dataclass(frozen=True)
class UnityPosition:
    """
    Value Object que representa la posicion de un nodo en el
    espacio 3D de Unity

    Es inmutable (frozen=True): Una vez creada, no se puede
    modificar. Si la posicion cambia, se crea una nueva instancia.

    Attributes:
        x: Coordenada X en Unity (float).
        y: Coordenada Y en Unity (float).
        z: Coordenada Z en Unity (float).
    """
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __str__(self) -> str:
        """Retorna representacion entendible de la posicion de un nodo en Unity."""
        return f"Unity ({self.x}, {self.y}, {self.z})"
    
@dataclass(frozen=True)
class PhysicalPosition:
    """
    Value Object que representa la posicion fisica de un nodo en el
    espacio fisico de la maqueta.
    
    A diferencia de UnityPosition, es bidireccional porque
    la maqueta es una superficie plana.

    Attributes:
        x: Coordenada X en la maqueta (float).
        y: Coordenada Y en la maqueta (float).
    """
    x: float = 0.0
    y: float = 0.0

    def __str__(self):
        """Retorna representacion entendible de la posicion de un nodo en la maqueta."""
        return f"Posicion Fisica ({self.x}, {self.y})"
    
# =============================================================
# ENTIDADES DE DOMINIO
# Tienen identidad propia (ID), ciclo de vida y pueden cambiar.
# =============================================================

@dataclass
class House:
    """
    Entidad que representa una instalacion domotica completa.
    
    Es el contenedor raiz del sistema. Todos los nodos,
    aristas y alias pertenecen a una casa especifica.

    Attributes:
        name: Nombre descriptivo de la casa.
        description: Descripcion opcional de la instalacion.
        id: Identificador unico asignado por la base de datos.
        created_at: Fecha y hora de creacion.
        updated_at: Fecha y hora de la ultima actualizacion.
    """
    name: str
    description: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def create(cls, name: str, description: Optional[str] = None) -> "House":
        """
        Factory Method: Crea una nueva casa validando sus datos.
        
        Centraliza la creacion garantizando que el nombre
        no este vacio antes de construir el objeto.

        Args:
            name: Nombre de la casa. No puede estar vacio.
            description: Descripcion opcional de la instalacion.

        Returns:
            Nueva instancia de House lista para ser guardada en la base de datos.

        Raises:
            ValueError: Si el nombre esta vacio o solo tiene espacios.
        """
        if not name or name.strip() == "":
            raise ValueError("El nombre de la casa no puede estar vacio.")
        
        return cls(name=name.strip(), description=description)
    
@dataclass
class NodeAlias:
    """
    Entidad que representa un alias de voz para un nodo.
    
    ARIA usa estos alias para reconocer a que nodo se refiere
    el usuario cuando da un comando de voz. Un nodo puede tener
    multiples alias (ej: 'sala', 'living', 'sala de estar').

    Attributes:
        node_id: ID del nodo al que pertenece este alias.
        alias: Texto del alias en minusculas normalizado.
        id: Identificador unico asignado por la base de datos.
        created_at: Fecha y hora de creacion.
    """
    node_id: int
    alias: str
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    @classmethod
    def create(cls, node_id: int, alias: str) -> "NodeAlias":
        """
        Factory Method: Crea un alias normalizando su texto a minusculas.
        
        Normaliza el alias a minusculas y sin espacios extras
        para garantizar busquedas consistentes por voz.

        Args:
            node_id: ID del nodo al que pertenece este alias.
            alias: Texto del alias. No puede estar vacio.
        
        Returns:
            Nueva instancia de NodeAlias normalizada

        Raises:
            ValueError: Si el alias esta vacio
        """

        if not alias or alias.strip() == "":
            raise ValueError("El alias no puede estar vacio.")
        
        return cls(node_id=node_id, alias=alias.strip().lower())
    
@dataclass
class NodeEdge:
    """
    Entidad que representa una arista del grafo de navegacion.
    
    Conecta dos nodos entre si. Puede ser bidireccional
    (el agente va y vuelve) o unidireccional (solo ida).
    El peso define el costo de recorrer esta arista, util
    para algoritmos de pathfinding como Dijkstra o A*.

    Attributes:
        from_node_id: ID del nodo de origen.
        to_node_id: ID del nodo de destino.
        weight: Costo de recorrer esta arista. Por defecto 1.0.
        is_bidirectional: Indica si la arista es bidireccional (True) o unidireccional (False).
        id: Identificador unico asignado por la base de datos.
        created_at: Fecha y hora de creacion.
    """
    from_node_id: int
    to_node_id: int
    weight: float = 1.0
    is_bidirectional: bool = True
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    @classmethod
    def create(
        cls, 
        from_node_id: int, 
        to_node_id: int, 
        weight: float = 1.0, 
        is_bidirectional: bool = True
    ) -> "NodeEdge":
        """
        Factory Method: Crea una nueva arista validando sus datos.

        Args:
            from_node_id: ID del nodo de origen. No puede ser igual a to_node_id.
            to_node_id: ID del nodo de destino. No puede ser igual a from_node_id.
            weight: Costo de recorrer esta arista. Debe ser positivo mayor a 0.
            is_bidirectional: Indica si la arista es bidireccional (True) o unidireccional (False).

        Returns:
            Nueva instancia de NodeEdge lista para ser guardada en la base de datos.
        
        Raises:
            ValueError: Si los nodos son el mismo o el peso es invalido
        """
        if from_node_id == to_node_id:
            raise ValueError("Un nodo no puede conectarse consigo mismo.")
        
        if weight <= 0:
            raise ValueError("El peso de la arista debe ser un numero positivo mayor a 0.")
        
        return cls(
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            weight=weight,
            is_bidirectional=is_bidirectional
        )
    
@dataclass
class Node:
    """
    Entidad central del sistema: representa un nodo del grafo
    de navegacion dentro de una casa domotica.

    Un nodo puede ser:
        - 'room': Una habitacion con nombre visible al usuario.
        - 'waypoint': Un punto intermedio de navegacion sin nombre
            visible, usado para guiar al agente por el grafo.

    La separacion entre internal_name y display_name garantiza
    que los cambios cosmeticos del usuario no afecten la logica
    de navegacion interna del sistema.

    Attributes:
        house_id: ID de la casa a la que pertenece.
        node_type: Tipo del nodo ('room' o 'waypoint').
        internal_name: Nombre tecnico inmutable usado por el sistema.
        display_name: Nombre visible y editable por el usuario.
        unity_position: Posicion 3D en Unity (Value Object).
        physical_position: Posicion 2D en la maqueta (Value Object).
        status: Estado del nodo ('active' o 'inactive').
        aliases: Lista de alias de voz asociados a este nodo.
        id: Identificador unico asignado por la base de datos.
        created_at: Fecha y hora de creacion.
        updated_at: Fecha y hora de ultima modificacion.
    """
    house_id: str
    node_type: str
    internal_name: str
    display_name: str
    unity_position: UnityPosition = field(default_factory=UnityPosition)
    physical_position: Optional[PhysicalPosition] = None
    status: str = NODE_STATUS_ACTIVE
    aliases: list[NodeAlias] = field(default_factory=list)
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def create(
        cls,
        house_id: str,
        node_type: str,
        internal_name: str,
        display_name: str,
        unity_position: Optional[UnityPosition] = None,
        physical_position: Optional[PhysicalPosition] = None,
    ) -> "Node":
        """
        Factory Method: Crea un nodo validando todos sus datos.
        
        Centraliza la validacion garantizando que el nodo
        siempre nace en un estado valido y consistente.

        Args:
            house_id: ID de la casa propietaria del nodo.
            node_type: Tipo del nodo ('room' o 'waypoint').
            internal_name: Nombre tecnico unico e inmutable.
            display_name: Nombre visible al usuario.
            unity_position: Posicion 3D en Unity. Default (0,0,0).
            physical_position: Posicion 2D en maqueta. Opcional.

        Returns:
            Nueva instancia de Node lista para ser guardada en la base de datos.
        
        Raises:
            ValueError: Si el tipo, nombre interno o display estan
                vacios o son invalidos.
        """

        if node_type not in VALID_NODE_TYPES:
            raise ValueError(
                f"Tipo de nodo invalido: '{node_type}'. "
                f"Tipos validos: {VALID_NODE_TYPES}"
            )
        
        if not internal_name or internal_name.strip() == "":
            raise ValueError("El nombre interno del nodo no puede estar vacio.")
        
        if not display_name or display_name.strip() == "":
            raise ValueError("El nombre visible del nodo no puede estar vacio.")
        
        return cls(
            house_id=house_id,
            node_type=node_type,
            internal_name=internal_name.strip().upper(),
            display_name=display_name.strip(),
            unity_position=unity_position or UnityPosition(),
            physical_position=physical_position,
        )
    
    @property
    def is_room(self) -> bool:
        """
        Retorna True si el nodo es una habitacion visible.
        
        Returns:
            True si node_type es 'room', False si es 'waypoint'.
        """
        return self.node_type == NODE_TYPE_ROOM
    
    @property
    def is_active(self) -> bool:
        """
        Retorna True si el nodo esta activo en el sistema.
        
        Returns:
            True si status es 'active'.
        """
        return self.status == NODE_STATUS_ACTIVE
