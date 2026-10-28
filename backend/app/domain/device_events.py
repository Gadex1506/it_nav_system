"""
app/domain/device_events.py

Mensajes que los dispositivos fisicos cuentan al sistema.

Responsabilidad: Definir, sin depender de MQTT ni de ninguna libreria,
la forma de lo que "llega desde el mundo fisico": en que estado quedo
un dispositivo y si esta conectado o no.

Son objetos inmutables (frozen): un reporte describe algo que ya
ocurrio y no debe modificarse despues de creado.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DeviceStateReport:
    """
    Estado que un dispositivo reporto de si mismo.

    Attributes:
        device_key: Identificador fijo del dispositivo (ej: 'light_sala').
        state: Estado como texto ('on', 'off'; las puertas usaran otros).
        timestamp_ms: Milisegundos desde que arranco el ESP32 (opcional).
    """

    device_key: str
    state: str
    timestamp_ms: Optional[int] = None


@dataclass(frozen=True)
class DeviceAvailabilityReport:
    """
    Aviso de conexion de un dispositivo (Last Will de MQTT).

    Attributes:
        device_key: Identificador fijo del dispositivo.
        online: True si esta conectado, False si se cayo.
    """

    device_key: str
    online: bool


@dataclass(frozen=True)
class BoardAvailabilityReport:
    """
    Aviso de conexion de una PLACA ESP32 (su Last Will de MQTT).

    Una placa maneja varios dispositivos (luces y puertas) con una sola
    conexion, y una conexion solo tiene un Last Will. Por eso la caida se
    avisa por la placa y no por cada dispositivo.

    Attributes:
        board_id: Identificador de la placa (ej: 'casa').
        online: True si esta conectada, False si se cayo.
    """

    board_id: str
    online: bool