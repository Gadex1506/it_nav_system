"""
# app/presentation/routers/user_router.py

Router de endpoints disponibles para el usuario final.

Responsabilidad: Exponer unicamente las operaciones seguras que
el usuario puede realizar desde el panel web como consultar los nodos de su casa,
renombrarlos y gestionar sus alias de voz.

El usuario NUNCA puede: ver otras casas,crear nodos, eliminar nodos, modificar
posiciones Unity, crear aristas ni eliminar aristas.

Principios SOLID aplicados:
    - S: Solo gestiona rutas de acceso para el usuario final.
    - I: Interfaz minima y especifica, sin exponer operaciones
    que el usuario no debe poder realizar.
"""

from fastapi import APIRouter, HTTPException, status, Depends

# SCHEMAS
from app.presentation.schemas import(
    NodeResponse, NodeUpdateDisplayNameRequest,
    AliasCreateRequest, AliasResponse,
    MessageResponse,
)

# SERVICES
from app.application.house_service import HouseService
from app.application.node_service import NodeService

# INFRASTRUCTURE
from app.infrastructure.database import get_db
from app.infrastructure.repositories.house_repository import SQLiteHouseRepository
from app.infrastructure.repositories.node_repository import SQLiteNodeRepository

# ROUTERS
from app.presentation.routers.dev_router import _node_to_response


# Prefijo /user el cual identifica estos endpoints como
# exclusivos para el usuario

ROUTER_PREFIX="/user"
ROUTER_TAG="User Panel"

router = APIRouter(prefix=ROUTER_PREFIX, tags=[ROUTER_TAG])

def get_node_service() -> NodeService:
    """
        Construye y retorna NodeService con sus dependencias
        para el contexto del usuario final.

        Returns:
            NodeService listo para usar con SQLite.
    """
    connection = get_db()

    return NodeService(
        SQLiteNodeRepository(connection),
        SQLiteHouseRepository(connection)
    )

def get_active_house_id() -> int:
    """
    Resuelve el ID de la casa activa (la de menor ID existente).

    Raises:
        HTTPException 404: Si no hay ninguna casa registrada.
    """
    service = HouseService(SQLiteHouseRepository(get_db()))
    try:
        return service.get_active_house().id
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))

# --- Endpoints de consulta ------------------------------------------

@router.get(
    "/nodes",
    response_model=list[NodeResponse],
    summary="Listar nodos de la casa activa"
)
async def get_nodes(
    service: NodeService = Depends(get_node_service),
    active_house_id: int = Depends(get_active_house_id)
) -> list[NodeResponse]:
    """
    Retorna todos los nodos activos de la casa configurada en el sistema.

    El usuario no elige la casa, el sistema ya sabe a cual
    pertenece esta instalacion mediante ACTIVE_HOUSE_ID en config.py.
    """
    try:
        nodes = service.get_nodes_by_house(active_house_id)
        return [_node_to_response(node) for node in nodes]
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error)
        )

@router.get(
    "/nodes/{node_id}",
    response_model=NodeResponse,
    summary="Obtener detalle de un nodo"
)
async def get_node(
    node_id: int,
    service: NodeService = Depends(get_node_service)
) -> NodeResponse:
    """Retorna el detalle completo de un nodo incluyendo sus alias."""
    node = service.get_node(node_id)

    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe un nodo con ID {node_id}."
        )
    
    return _node_to_response(node)



# --- Endpoints de edicion. Solo los permitidos para el usuario ----------------------

@router.patch(
    "/nodes/{node_id}/display-name",
    response_model=NodeResponse,
    summary="Renombrar un nodo"
)
async def rename_node(
    node_id: int,
    request: NodeUpdateDisplayNameRequest,
    service: NodeService = Depends(get_node_service)
) -> NodeResponse:
    """
    Actualiza el nombre visible de un nodo.

    Este es el endpoint principal que el usuario usa desde
    el panel web para personalizar como se llaman sus habitaciones.
    El internal_name nunca cambia.
    """

    try:
        node = service.rename_node(node_id, request.display_name)
        return _node_to_response(node)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )


@router.post(
    "/nodes/{node_id}/aliases",
    response_model=AliasResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Agregar alias de voz a un nodo"
)
async def add_alias(
    node_id: int,
    request: AliasCreateRequest,
    service: NodeService = Depends(get_node_service)
) -> AliasResponse:
    """
    Agrega un alias de voz para que ARIA reconozca este nodo
    con un nombre adicional.
    """

    try:
        alias = service.add_alias_to_node(node_id, request.alias)
        
        return AliasResponse(
            id=alias.id,
            node_id=alias.node_id,
            alias=alias.alias,
            created_at=str(alias.created_at) if alias.created_at else None,
        )
    
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )


@router.delete(
    "/nodes/{node_id}/aliases/{alias_id}",
    response_model=MessageResponse,
    summary="Eliminar un alias de voz"
)
async def delete_alias(
    node_id: int,
    alias_id: int,
    service: NodeService = Depends(get_node_service)
) -> MessageResponse:

    """Elimina un alias de voz especifico de un nodo."""
    try:
        service.delete_alias(alias_id)

        return MessageResponse(
            success=True,
            message=f"Alias {alias_id} eliminado correctamente."
        )
    
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )