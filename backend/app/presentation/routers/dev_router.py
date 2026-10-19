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

from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query

# SCHEMAS
from app.presentation.schemas import (
    HouseCreateRequest, HouseResponse,
    NodeCreateRequest, NodeResponse,
    NodeUpdatePhysicalPositionRequest,
    EdgeCreateRequest, EdgeResponse,
    AliasCreateRequest, AliasResponse,
    MessageResponse, UnityPositionSchema,
    PhysicalPositionSchema, HouseSummaryResponse,
    HousesOverviewResponse, DeviceCreateRequest, 
    DeviceUpdateDisplayNameRequest, DeviceResponse,
)

from app.presentation.security import require_dev_key

# REPOSITORIES
from app.domain.exceptions import HouseDeletionNotConfirmedError, DeviceKeyAlreadyExistsError

# SERVICES
from app.application.house_service import HouseService
from app.application.node_service import NodeService
from app.application.device_service import DeviceService

# INFRASTRUCTURE
from app.infrastructure.database import get_db
from app.infrastructure.repositories.house_repository import SQLiteHouseRepository
from app.infrastructure.repositories.node_repository import SQLiteNodeRepository
from app.infrastructure.repositories.device_repository import SQLiteDeviceRepository

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

def get_device_service() -> DeviceService:
    """
    Construye y retorna el DeviceService con sus dependencias.

    Returns:
        DeviceService listo para usar con SQLite.
    """
    connection = get_db()
    return DeviceService(
        SQLiteDeviceRepository(connection),
        SQLiteNodeRepository(connection),
    )

# --- Endpoints de House ------------------------------------------

@router.post(
    "/houses",
    response_model=HouseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una nueva casa (requiere X-Dev-Key)",
    dependencies=[Depends(require_dev_key)]
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

@router.get(
    "/houses/overview",
    response_model=HousesOverviewResponse,
    summary="Resumen de casas con cantidad de nodos (requiere X-Dev-Key)",
    dependencies=[Depends(require_dev_key)]
)
async def get_houses_overview(
    service: HouseService = Depends(get_house_service)
) -> HousesOverviewResponse:
    """Lista las casas con su cantidad de nodos y marca la casa activa."""
    overview = service.get_houses_overview()
    active_id = min((h.id for h, _ in overview), default=None)

    houses = [
        HouseSummaryResponse(
            id=h.id,
            name=h.name,
            description=h.description,
            created_at=str(h.created_at) if h.created_at else None,
            updated_at=str(h.updated_at) if h.updated_at else None,
            node_count=node_count,
            is_active=(h.id == active_id),
        )
        for h, node_count in overview
    ]

    return HousesOverviewResponse(active_house_id=active_id, houses=houses)


@router.delete(
    "/houses/{house_id}",
    response_model=MessageResponse,
    summary="Eliminar una casa con todo lo relacionado (requiere X-Dev-Key)",
    dependencies=[Depends(require_dev_key)]
)
async def delete_house(
    house_id: int,
    confirm_name: str = Query(description="Nombre exacto de la casa para confirmar"),
    service: HouseService = Depends(get_house_service)
) -> MessageResponse:
    """Elimina una casa y, en una transaccion, sus nodos, alias y aristas."""
    try:
        house = service.delete_house(house_id, confirm_name)
        return MessageResponse(
            success=True,
            message=f"Casa '{house.name}' eliminada junto con todos sus datos."
        )

    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))

    except HouseDeletionNotConfirmedError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


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

# --- Endpoints de Device (luces y puertas) ----------------------

@router.post(
    "/devices",
    response_model=DeviceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un dispositivo en una habitacion (requiere X-Dev-Key)",
    dependencies=[Depends(require_dev_key)]
)
async def create_device(
    request: DeviceCreateRequest,
    service: DeviceService = Depends(get_device_service)
) -> DeviceResponse:
    """
    Registra una luz o una puerta en una habitacion.

    El device_key es el identificador fijo que usara el contrato MQTT
    (por ejemplo light_living). No puede repetirse.
    """

    try:
        device = service.create_device(
            node_id=request.node_id,
            device_type=request.device_type,
            device_key=request.device_key,
            display_name=request.display_name,
        )
        return _device_to_response(device)

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )

    except DeviceKeyAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error)
        )

@router.get(
    "/devices",
    response_model=list[DeviceResponse],
    summary="Listar dispositivos de una casa o de una habitacion"
)
async def get_devices(
    house_id: Optional[int] = Query(default=None, description="ID de la casa"),
    node_id: Optional[int] = Query(default=None, description="ID de la habitacion"),
    device_type: Optional[str] = Query(default=None, description="'light' o 'door'"),
    service: DeviceService = Depends(get_device_service)
) -> list[DeviceResponse]:
    """
    Lista dispositivos. Debe indicarse house_id o node_id (uno de los dos).
    El filtro device_type es opcional.
    """

    if (house_id is None) == (node_id is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Indica house_id o node_id (solo uno de los dos)."
        )

    try:
        if node_id is not None:
            devices = service.get_devices_by_node(node_id, device_type)
        else:
            devices = service.get_devices_by_house(house_id, device_type)

        return [_device_to_response(d) for d in devices]

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )

@router.patch(
    "/devices/{device_id}/display-name",
    response_model=DeviceResponse,
    summary="Renombrar un dispositivo"
)
async def rename_device(
    device_id: int,
    request: DeviceUpdateDisplayNameRequest,
    service: DeviceService = Depends(get_device_service)
) -> DeviceResponse:
    """Cambia el nombre visible. El device_key nunca cambia."""

    try:
        device = service.rename_device(device_id, request.display_name)
        return _device_to_response(device)

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error)
        )

@router.delete(
    "/devices/{device_id}",
    response_model=MessageResponse,
    summary="Eliminar un dispositivo (requiere X-Dev-Key)",
    dependencies=[Depends(require_dev_key)]
)
async def delete_device(
    device_id: int,
    service: DeviceService = Depends(get_device_service)
) -> MessageResponse:
    """Elimina un dispositivo de su habitacion."""

    try:
        service.delete_device(device_id)

        return MessageResponse(
            success=True,
            message=f"Dispositivo {device_id} eliminado correctamente."
        )

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
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

def _device_to_response(device) -> DeviceResponse:
    """
    Convierte un objeto Device del dominio a su schema de respuesta.

    Args:
        device: Instancia de Device del dominio.

    Returns:
        DeviceResponse listo para serializar como JSON.
    """

    return DeviceResponse(
        id=device.id,
        node_id=device.node_id,
        device_type=device.device_type,
        device_key=device.device_key,
        display_name=device.display_name,
        created_at=str(device.created_at) if device.created_at else None,
        updated_at=str(device.updated_at) if device.updated_at else None,
    )