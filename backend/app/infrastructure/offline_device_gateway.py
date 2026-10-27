"""
app/infrastructure/offline_device_gateway.py

Pasarela "apagada": se usa cuando MQTT esta deshabilitado en la configuracion.

Patron aplicado:
    - Null Object: en lugar de poner "if gateway is None" por todo el
    codigo, se entrega una pasarela que cumple el contrato pero no hace
    nada y avisa con claridad que no puede enviar. Analogia: un telefono
    sin linea; se puede marcar, pero siempre responde "sin servicio".
"""

import logging

from app.domain.exceptions import GatewayUnavailableError
from app.domain.interfaces import (
    AbstractDeviceGateway,
    AvailabilityListener,
    StateListener,
)

logger = logging.getLogger(__name__)


class OfflineDeviceGateway(AbstractDeviceGateway):
    """Pasarela que nunca se conecta y rechaza toda orden."""

    def start(self) -> None:
        logger.info("MQTT deshabilitado: la pasarela de dispositivos no se conectara.")

    def stop(self) -> None:
        return None

    @property
    def is_connected(self) -> bool:
        return False

    def publish_light_command(self, device_key: str, state: str) -> None:
        raise GatewayUnavailableError("La pasarela MQTT esta deshabilitada.")

    def set_state_listener(self, listener: StateListener) -> None:
        return None

    def set_availability_listener(self, listener: AvailabilityListener) -> None:
        return None
