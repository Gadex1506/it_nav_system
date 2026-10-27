"""
app/presentation/gateway_router.py

Endpoints de DESARROLLO para probar la pasarela hacia los dispositivos.

Responsabilidad: Permitir mandar una orden a una luz y ver el ultimo
estado que reportaron los dispositivos. Todos exigen la clave de
desarrollador (X-Dev-Key). Mas adelante, el flujo de voz llamara al
DeviceControlService directamente o a un endpoint de usuario propio.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.device_control_service import DeviceControlService
from app.application.device_state_store import DeviceLiveStatus
from app.domain.exceptions import DeviceNotFoundError, GatewayUnavailableError
from app.infrastructure.gateway_provider import get_device_gateway, get_state_store
from app.presentation.routers.dev_router import get_device_service
from app.presentation.gateway_schemas import (
    DeviceLiveStatusResponse,
    GatewayStatusResponse,
    LightCommandRequest,
    LightCommandResponse,
)
from app.presentation.security import require_dev_key

router = APIRouter(
    prefix="/dev/gateway",
    tags=["Gateway"],
    dependencies=[Depends(require_dev_key)],
)


def get_device_control_service() -> DeviceControlService:
    """Ensambla el servicio con la pasarela y el almacen unicos."""
    return DeviceControlService(
        device_service=get_device_service(),
        gateway=get_device_gateway(),
        state_store=get_state_store(),
    )


def _to_response(live: DeviceLiveStatus) -> DeviceLiveStatusResponse:
    return DeviceLiveStatusResponse(
        device_key=live.device_key,
        state=live.state,
        online=live.online,
        last_update=live.last_update.isoformat() if live.last_update else None,
    )


@router.post(
    "/lights/{device_key}",
    response_model=LightCommandResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Encender o apagar una luz fisica",
)
async def set_light(
    device_key: str,
    request: LightCommandRequest,
    service: DeviceControlService = Depends(get_device_control_service),
) -> LightCommandResponse:
    """
    Envia la orden. Responde 202 (aceptada): significa que la orden salio
    hacia el broker, no que la luz ya cambio. El resultado real aparece en
    GET /dev/gateway/status cuando el ESP32 publique su estado.
    """
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


@router.get(
    "/status",
    response_model=GatewayStatusResponse,
    summary="Estado de la pasarela y de los dispositivos que han reportado",
)
async def get_gateway_status(
    service: DeviceControlService = Depends(get_device_control_service),
) -> GatewayStatusResponse:
    """Indica si hay conexion con el broker y lista el ultimo estado conocido."""
    return GatewayStatusResponse(
        connected=service.gateway_connected,
        devices=[_to_response(live) for live in service.get_all_live_status()],
    )


@router.get(
    "/devices/{device_key}/status",
    response_model=DeviceLiveStatusResponse,
    summary="Ultimo estado conocido de un dispositivo",
)
async def get_device_status(
    device_key: str,
    service: DeviceControlService = Depends(get_device_control_service),
) -> DeviceLiveStatusResponse:
    """404 si ese dispositivo todavia no ha reportado nada."""
    live = service.get_live_status(device_key)

    if live is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El dispositivo '{device_key}' aun no ha reportado su estado.",
        )

    return _to_response(live)
