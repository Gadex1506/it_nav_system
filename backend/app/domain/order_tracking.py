"""
app/domain/order_tracking.py

Resultado de una orden dada a un dispositivo fisico.

Responsabilidad: Definir, sin depender de MQTT ni de HTTP, que le puede
pasar a una orden: sigue esperando respuesta, se confirmo, el dispositivo
quedo en un estado distinto al pedido, o nunca respondio.

Analogia: el acuse de recibo de una carta certificada. Sabes cuando
la enviaste, y despues sabes si llego, si la recibieron con un problema
o si paso el plazo sin noticias.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class OrderOutcome(str, Enum):
    """Estado de una orden (el valor de texto es el que viaja por la API)."""

    PENDING = "pending"          # Enviada, aun dentro del plazo
    CONFIRMED = "confirmed"      # El dispositivo reporto el estado esperado
    MISMATCH = "mismatch"        # El dispositivo reporto un estado distinto o de fallo
    NO_RESPONSE = "no_response"  # Paso el plazo sin ningun estado nuevo


@dataclass(frozen=True)
class OrderReport:
    """
    Foto de la ultima orden de un dispositivo.

    Attributes:
        order_id: Numero consecutivo (sirve para no avisar dos veces de la misma orden).
        device_key: Dispositivo al que se le dio la orden.
        requested: Lo que se pidio ('on', 'off', 'open', 'close').
        outcome: Como va o como termino.
        sent_at: Hora UTC en que salio la orden.
        reported_state: Estado con el que el dispositivo respondio, si respondio.
        detail: Frase corta que explica el resultado.
    """

    order_id: int
    device_key: str
    requested: str
    outcome: OrderOutcome
    sent_at: datetime
    reported_state: Optional[str] = None
    detail: str = ""
