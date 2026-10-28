"""
app/application/device_state_store.py

Memoria del "ultimo estado conocido" de cada dispositivo fisico.

Responsabilidad: Guardar en memoria lo que cada ESP32 ha contado
(estado de los dispositivos y conexion de las placas). NO va a la base
de datos a proposito: el estado de una luz cambia todo el tiempo y la
fuente de verdad es el propio dispositivo, que ademas lo publica con
'retain' al reconectar.

Regla de conexion (contrato v0.3): un dispositivo esta conectado segun
su PLACA, porque una placa maneja varios dispositivos con un solo Last Will.
    - Placa offline                        -> dispositivo offline (manda la placa).
    - Placa online/desconocida + el propio dispositivo aviso -> vale su aviso.
    - Placa online y el dispositivo no aviso -> online.
    - Nada se sabe                         -> None.

Seguridad entre hilos: los reportes llegan desde el hilo de red de MQTT
mientras FastAPI lee desde otros hilos, por eso todo pasa por un Lock.
"""

import threading
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Optional

from app import config
from app.domain.device_events import (
    BoardAvailabilityReport,
    DeviceAvailabilityReport,
    DeviceStateReport,
)


@dataclass(frozen=True)
class DeviceLiveStatus:
    """
    Ultimo estado conocido de un dispositivo.

    Attributes:
        device_key: Identificador fijo del dispositivo.
        state: Ultimo estado reportado, o None si aun no ha reportado.
        online: True/False segun la regla de conexion, o None si no se sabe.
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
        self._boards_online: dict[str, bool] = {}

    def update_state(self, report: DeviceStateReport) -> None:
        """Guarda el estado que acaba de reportar un dispositivo."""
        with self._lock:
            current = self._statuses.get(report.device_key, DeviceLiveStatus(report.device_key))
            self._statuses[report.device_key] = replace(
                current, state=report.state, last_update=self._now()
            )

    def update_availability(self, report: DeviceAvailabilityReport) -> None:
        """Guarda el aviso propio de un dispositivo (opcional desde la v0.3)."""
        with self._lock:
            current = self._statuses.get(report.device_key, DeviceLiveStatus(report.device_key))
            self._statuses[report.device_key] = replace(
                current, online=report.online, last_update=self._now()
            )

    def update_board_availability(self, report: BoardAvailabilityReport) -> None:
        """Guarda si una placa esta conectada o se cayo."""
        with self._lock:
            self._boards_online[report.board_id] = report.online

    def get(self, device_key: str) -> Optional[DeviceLiveStatus]:
        """Devuelve el estado conocido o None si nunca ha reportado nada."""
        with self._lock:
            status = self._statuses.get(device_key)
            return None if status is None else self._with_effective_online(status)

    def get_all(self) -> list[DeviceLiveStatus]:
        """Devuelve el estado de todos los dispositivos que han reportado."""
        with self._lock:
            return [self._with_effective_online(s) for s in self._statuses.values()]

    # ─── Internos (se llaman con el Lock ya tomado) ──────────────────────

    def _with_effective_online(self, status: DeviceLiveStatus) -> DeviceLiveStatus:
        """Aplica la regla de conexion mezclando el aviso del dispositivo y el de su placa."""
        board_online = self._boards_online.get(config.MQTT_HOUSE_BOARD_ID)

        if board_online is False:
            effective = False
        elif status.online is not None:
            effective = status.online
        else:
            effective = board_online

        return replace(status, online=effective)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)