"""
# app/presentation/routers/dev_router.py

Router de endpoints EXCLUSIVOS PARA DESARROLLADORES.

Responsabilidad: Exponer las operaciones completas de creacion,
actualizacion y eliminacion de la estructura del sistema. Estos
endpoints son usados exclusivamente por Unity y el equipo de
desarrollo, nunca por el usuario final.

Principios SOLID aplicados:
    - S: Solo gestiona rutas de acceso para desarrolladores.
    - O: Nuevos endpoints de desarrollo se agregan aqui sin
    modificar el router de usuario.
"""

from fastapi import APIRouter, HTTPException, status, Depends

# SCHEMAS
from app.presentation.schemas import (
    HouseCreateRequest, HouseResponse,
    NodeCreateRequest, NodeResponse,
    NodeUpdatePhysicalPositionRequest,
    EdgeCreateRequest, EdgeResponse,
    AliasCreateRequest, AliasResponse,
    MessageResponse, UnityPositionSchema,
    PhysicalPositionSchema,
)

# SERVICES
from app.application.house_service import HouseService
from app.application.node_service import NodeService

# INFRASTRUCTURE
from app.infrastructure.database import get_db
from app.infrastructure.repositories.house_repository import SQLiteHouseRepository
from app.infrastructure.repositories.node_repository import SQLiteNodeRepository


# Prefijo /dev el cual identifica estos endpoints como
# exclusivos para el equipo de desarrollo y Unity

ROUTER_PREFIX="/dev"
ROUTER_TAG="Developer"

router = APIRouter(prefix=ROUTER_PREFIX, tags=[ROUTER_TAG])

def get_house_service() -> HouseService:
    """
    Construye y retorna el HouseService con sus dependencias.
    
    Este es el punto donde se ensambla la cadena completa:
    conexion -> repositorio -> servicio. FastAPI llama a esta
    funcion automaticamente en cada request que se necesite.

    Returns:
        HouseService listo para usar con SQLite.
    """
    connection = get_db()
    repository = SQLiteHouseRepository(connection)
    return HouseService(repository)

def get_node_service() -> NodeService:
    """
    Construye y retorna el NodeService con sus dependencias.
    
    Returns:
        NodeService listo para usar con SQLite.
    """
    connection = get_db()
    node_repository = SQLiteNodeRepository(connection)
    house_repository = SQLiteHouseRepository(connection)
    return NodeService(node_repository, house_repository)


# --- Endpoints de House ------------------------------------------

@router.post(
    "/houses",
    response_model=HouseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una nueva casa"
)
async def create_house(
    request: HouseCreateRequest,
    service: HouseService = Depends(get_house_service)
) -> HouseResponse:
    """
    Registra una nueva instalacion domotica en el sistema.
    
    Usado por el desarrollador para inicializar una nueva casa
    antes de registrar sus nodos desde Unity.
    """

    try:
        house = service.create_house(
            name=request.name,
            description=request.description
        )

        return HouseResponse(
            id=house.id,
            name=house.name,
            description=house.description,
            created_at=str(house.created_at) if house.created_at else None,
            updated_at=str(house.updated_at) if house.updated_at else None,
        )
    
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )


@router.get(
    "/houses",
    response_model=list[HouseResponse],
    summary="Listar todas las casas registradas"
)
async def get_all_houses(
    service: HouseService = Depends(get_house_service)
) -> list[HouseResponse]:
    """Retorna todas las casas registradas en el sistema."""

    houses = service.get_all_houses()

    return [
        HouseResponse(
            id=h.id,
            name=h.name,
            description=h.description,
            created_at=str(h.created_at) if h.created_at else None,
            updated_at=str(h.updated_at) if h.updated_at else None,
        )
        for h in houses
    ]


# --- Endpoints de Node ------------------------------------------

@router.post(
    "/nodes",
    response_model=NodeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo nodo desde Unity"
)
async def create_node(
    request: NodeCreateRequest,
    service: NodeService = Depends(get_node_service)
) -> NodeResponse:
    """
    Registra un nuevo nodo del grafo de navegacion.
    
    Llamado desde el Editor de Unity cuando el desarrollador
    posiciona un nuevo nodo en la escena y presiona "Registrar".
    La posicion Unity (x, y, z) se captura automaticamente.
    """
    
    try:
        node = service.create_node(
            house_id=request.house_id,
            node_type=request.node_type,
            internal_name=request.internal_name,
            display_name=request.display_name,
            unity_x=request.unity_x,
            unity_y=request.unity_y,
            unity_z=request.unity_z,
            physical_x=request.physical_x,
            physical_y=request.physical_y,
        )

        return _node_to_response(node)
    
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )


@router.delete(
    "/nodes/{node_id}",
    response_model=MessageResponse,
    summary="Eliminar un nodo"
)
async def delete_node(
    node_id: int,
    service: NodeService = Depends(get_node_service)
) -> MessageResponse:
    """
    Elimina un nodo y en cascada sus alias y aristas.
    Solo disponible para el desarrollador.
    """

    try:
        service.delete_node(node_id)

        return MessageResponse(
            success=True,
            message=f"Nodo {node_id} eliminado correctamente."
        )
    
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error)
        )


@router.patch(
    "/nodes/{node_id}/physical-position",
    response_model=NodeResponse,
    summary="Actualizar posición física del nodo en la maqueta."
)
async def update_physical_position(
    node_id: int,
    request: NodeUpdatePhysicalPositionRequest,
    service: NodeService = Depends(get_node_service)
) -> NodeResponse:
    """
    Actualiza las coordenadas fisicas de un nodo en la maqueta.
    La posicion Unity nunca cambia desde aqui, solo la fisica.
    """

    try:
        node = service.update_physical_position(node_id, request.x, request.y)
        return _node_to_response(node)
    
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error)
        )


# --- Endpoints de Edge ------------------------------------------

@router.post(
    "/edges",
    response_model=EdgeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una nueva arista desde Unity"
)
async def create_edge(
    request: EdgeCreateRequest,
    service: NodeService = Depends(get_node_service)
) -> EdgeResponse:
    """Registra una conexion entre dos nodos del grafo."""

    try:
        edge = service.add_edge(
            from_node_id=request.from_node_id,
            to_node_id=request.to_node_id,
            weight=request.weight,
            is_bidirectional=request.is_bidirectional,
        )

        return EdgeResponse(
            id=edge.id,
            from_node_id=edge.from_node_id,
            to_node_id=edge.to_node_id,
            weight=edge.weight,
            is_bidirectional=edge.is_bidirectional,
            created_at=str(edge.created_at) if edge.created_at else None,
        )
    
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )


@router.delete(
    "/edges/{edge_id}",
    response_model=MessageResponse,
    summary="Eliminar una arista del grafo"
)
async def delete_edge(
    edge_id: int,
    service: NodeService = Depends(get_node_service)
) -> MessageResponse:
    """Elimina una arista del grafo de navegacion"""

    try:
        service.delete_edge(edge_id)

        return MessageResponse(
            success=True,
            message=f"Arista {edge_id} eliminada correctamente."
        )
    
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error)
        )


# --- Endpoints de Alias (dev tambien puede gestionar alias) ----------------------

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
    """Agrega un alias de voz a un nodo respetando el limite maximo."""

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


# --- Funcion auxiliar privada --------------------------------

def _node_to_response(node) -> NodeResponse:
    """
    Convierte un objeto Node del dominio a su schema de respuesta.
    
    Funcion auxiliar que evita duplicar esta conversion en cada
    endpoint que necesite retornar un NodeResponse.

    Args:
        node: Instancia de Node del dominio.

    Returns:
        NodeResponse listo para serializar como JSON.
    """

    return NodeResponse(
        id=node.id,
        house_id=node.house_id,
        node_type=node.node_type,
        internal_name=node.internal_name,
        display_name=node.display_name,
        unity_position=UnityPositionSchema(
            x=node.unity_position.x,
            y=node.unity_position.y,
            z=node.unity_position.z,
        ),
        physical_position=PhysicalPositionSchema(
            x=node.physical_position.x,
            y=node.physical_position.y,
        ) if node.physical_position else None,
        status=node.status,
        aliases=[
            AliasResponse(
                id=a.id,
                node_id=a.node_id,
                alias=a.alias,
                created_at=str(a.created_at) if a.created_at else None,
            )
            for a in node.aliases
        ],
        created_at=str(node.created_at) if node.created_at else None,
        updated_at=str(node.updated_at) if node.updated_at else None,
    )