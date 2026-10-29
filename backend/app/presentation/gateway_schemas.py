"""
app/presentation/gateway_schemas.py

Schemas de entrada y salida de los endpoints de la pasarela.
"""

from typing import Optional

from pydantic import BaseModel, Field


class LightCommandRequest(BaseModel):
    """Orden para una luz."""

    state: str = Field(..., description="'on' para encender, 'off' para apagar")


class LightCommandResponse(BaseModel):
    """Confirmacion de que la orden SALIO (no de que la luz ya cambio)."""

    device_key: str
    requested_state: str
    message: str


class DeviceLiveStatusResponse(BaseModel):
    """Ultimo estado conocido de un dispositivo."""

    device_key: str
    state: Optional[str] = None
    online: Optional[bool] = None
    last_update: Optional[str] = Field(None, description="Hora UTC del ultimo reporte (ISO 8601)")
    last_order: Optional["OrderReportResponse"] = Field(
        None, description="Resultado de la ultima orden dada a este dispositivo, si hubo alguna"
    )


class GatewayStatusResponse(BaseModel):
    """Estado de la pasarela y de los dispositivos que han reportado."""

    connected: bool
    devices: list[DeviceLiveStatusResponse]


class DoorCommandRequest(BaseModel):
    """Orden para una puerta."""

    action: str = Field(..., description="'open' para abrir, 'close' para cerrar")
    hold_ms: Optional[int] = Field(
        None,
        description="Cierre de seguridad en milisegundos (solo con 'open'). Si se omite, "
        "la puerta usa su valor por defecto.",
    )


class DoorCommandResponse(BaseModel):
    """Confirmacion de que la orden SALIO (no de que la puerta ya se movio)."""

    device_key: str
    requested_action: str
    hold_ms: Optional[int] = None
    message: str


class AllLightsCommandRequest(BaseModel):
    """Orden para TODAS las luces de una casa."""

    house_id: int = Field(..., gt=0, description="ID de la casa")
    state: str = Field(..., description="'on' para encender, 'off' para apagar")


class AllLightsCommandResponse(BaseModel):
    """Confirmacion de que la orden SALIO hacia las luces indicadas."""

    house_id: int
    requested_state: str
    device_keys: list[str]
    message: str


class OrderReportResponse(BaseModel):
    """Resultado de la ultima orden dada a un dispositivo."""

    order_id: int
    device_key: str
    requested: str
    outcome: str = Field(..., description="pending, confirmed, mismatch o no_response")
    sent_at: str = Field(..., description="Hora UTC en que salio la orden (ISO 8601)")
    reported_state: Optional[str] = None
    detail: str = ""