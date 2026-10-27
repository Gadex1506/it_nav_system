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


class GatewayStatusResponse(BaseModel):
    """Estado de la pasarela y de los dispositivos que han reportado."""

    connected: bool
    devices: list[DeviceLiveStatusResponse]
