"""
app/application/device_state_store.py

Memoria del "ultimo estado conocido" de cada dispositivo fisico.

Responsabilidad: Guardar en memoria lo que cada ESP32 ha contado
(estado y si esta conectado). NO va a la base de datos a proposito:
el estado de una luz cambia todo el tiempo y la fuente de verdad es el
propio dispositivo, que ademas lo publica con 'retain' al reconectar.

Seguridad entre hilos: los reportes llegan desde el hilo de red de MQTT
mientras FastAPI lee desde otros hilos, por eso todo pasa por un Lock.
"""

import threading
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Optional

from app.domain.device_events import DeviceAvailabilityReport, DeviceStateReport


@dataclass(frozen=True)
class DeviceLiveStatus:
    """
    Ultimo estado conocido de un dispositivo.

    Attributes:
        device_key: Identificador fijo del dispositivo.
        state: Ultimo estado reportado, o None si aun no ha reportado.
        online: True/False segun su ultimo aviso, o None si no se sabe.
        last_update: Cuando llego el ultimo reporte (hora del servidor, UTC).
    """

    device_key: str
    state: Optional[str] = None
    online: Optional[bool] = None
    last_update: Optional[datetime] = None


class DeviceStateStore:
    """Almacen en memoria, seguro entre hilos, del estado de los dispositivos."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._statuses: dict[str, DeviceLiveStatus] = {}

    def update_state(self, report: DeviceStateReport) -> None:
        """Guarda el estado que acaba de reportar un dispositivo."""
        with self._lock:
            current = self._statuses.get(report.device_key, DeviceLiveStatus(report.device_key))
            self._statuses[report.device_key] = replace(
                current, state=report.state, last_update=self._now()
            )

    def update_availability(self, report: DeviceAvailabilityReport) -> None:
        """Guarda si el dispositivo esta conectado o se cayo."""
        with self._lock:
            current = self._statuses.get(report.device_key, DeviceLiveStatus(report.device_key))
            self._statuses[report.device_key] = replace(
                current, online=report.online, last_update=self._now()
            )

    def get(self, device_key: str) -> Optional[DeviceLiveStatus]:
        """Devuelve el estado conocido o None si nunca ha reportado nada."""
        with self._lock:
            return self._statuses.get(device_key)

    def get_all(self) -> list[DeviceLiveStatus]:
        """Devuelve el estado de todos los dispositivos que han reportado."""
        with self._lock:
            return list(self._statuses.values())

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
