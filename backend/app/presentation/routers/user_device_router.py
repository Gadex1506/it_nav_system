"""
app/presentation/routers/user_device_router.py

Endpoints de USUARIO para dar ordenes a la maqueta fisica.

Responsabilidad: Recibir las ordenes que Unity manda despues de ejecutar
la accion en la simulacion (luces y puertas) y
pasarlas al DeviceControlService. NO piden clave de desarrollador:
Unity no puede llevar una incrustada.

Seguridad: como no hay clave, el backend solo debe escuchar en la
propia maquina (INCLUSIVE_API_HOST, por defecto 127.0.0.1). Si algun
dia se expone en la red, hay que agregar autenticacion aqui.

Semantica: son ordenes "best effort" de Unity. Responden 202 cuando la
orden SALIO hacia el broker; el estado real lo confirma el ESP32 y se
consulta con /dev/gateway. Unity no espera ni depende de esta respuesta.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.device_control_service import DeviceControlService
from app.domain.exceptions import DeviceNotFoundError, GatewayUnavailableError
from app.presentation.gateway_schemas import (
    AllLightsCommandRequest,
    AllLightsCommandResponse,
    DoorCommandRequest,
    DoorCommandResponse,
    LightCommandRequest,
    LightCommandResponse,
    OrderReportResponse,
)
from app.config import ORDER_PROBLEM_VISIBLE_SECONDS
from app.presentation.routers.gateway_router import get_device_control_service, to_order_response

router = APIRouter(prefix="/user/devices", tags=["Dispositivos (usuario)"])


@router.post(
    "/lights",
    response_model=AllLightsCommandResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Encender o apagar TODAS las luces de una casa",
)
async def set_all_lights(
    request: AllLightsCommandRequest,
    service: DeviceControlService = Depends(get_device_control_service),
) -> AllLightsCommandResponse:
    """Una sola orden para toda la casa: si no hay conexion no se envia ninguna."""
    try:
        device_keys = service.set_all_lights(request.house_id, request.state)

    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))

    except GatewayUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error))

    return AllLightsCommandResponse(
        house_id=request.house_id,
        requested_state=request.state.strip().lower(),
        device_keys=device_keys,
        message="Orden enviada. El estado real lo confirmara cada dispositivo.",
    )


@router.post(
    "/lights/{device_key}",
    response_model=LightCommandResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Encender o apagar una luz",
)
async def set_light(
    device_key: str,
    request: LightCommandRequest,
    service: DeviceControlService = Depends(get_device_control_service),
) -> LightCommandResponse:
    """Orden para una luz identificada por su device_key (ej: light_sala)."""
    try:
        device = service.set_light(device_key, request.state)

    except DeviceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))

    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))

    except GatewayUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error))

    return LightCommandResponse(
        device_key=device.device_key,
        requested_state=request.state.strip().lower(),
        message="Orden enviada. El estado real lo confirmara el dispositivo.",
    )


@router.post(
    "/doors/{device_key}",
    response_model=DoorCommandResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Abrir o cerrar una puerta",
)
async def set_door(
    device_key: str,
    request: DoorCommandRequest,
    service: DeviceControlService = Depends(get_device_control_service),
) -> DoorCommandResponse:
    """
    Orden para una puerta (ej: door_banio). Unity la manda en el escenario A
    (sin robot) cuando el agente abre o cierra su puerta.
    """
    try:
        device = service.set_door(device_key, request.action, request.hold_ms)

    except DeviceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))

    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))

    except GatewayUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error))

    return DoorCommandResponse(
        device_key=device.device_key,
        requested_action=request.action.strip().lower(),
        hold_ms=request.hold_ms,
        message="Orden enviada. El estado real lo confirmara el dispositivo.",
    )


@router.get(
    "/orders/problems",
    response_model=list[OrderReportResponse],
    summary="Ordenes recientes que la maqueta no cumplio",
)
async def get_order_problems(
    service: DeviceControlService = Depends(get_device_control_service),
) -> list[OrderReportResponse]:
    """
    Lo consulta Unity cada pocos segundos. Devuelve solo problemas RECIENTES
    (sin respuesta o con estado distinto al pedido). Cada uno trae un order_id
    para que Unity no avise dos veces de la misma orden.
    """
    return [
        to_order_response(order)
        for order in service.get_recent_order_problems(ORDER_PROBLEM_VISIBLE_SECONDS)
    ]