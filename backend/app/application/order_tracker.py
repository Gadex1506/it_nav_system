"""
app/application/order_tracker.py

Recuerda la ULTIMA orden de cada dispositivo y decide si se cumplio.

Responsabilidad: Cuando el backend manda una orden la registra; cuando el
dispositivo reporta su estado, la resuelve. Si pasa el plazo sin respuesta,
la marca como "sin respuesta". Es lo que permite avisar "la luz no respondio".

Decisiones de diseno:
    - El plazo se evalua AL CONSULTAR (evaluacion perezosa), no con un
    temporizador: no hay hilos extra y es muy facil de probar con un reloj falso.
    - Solo se guarda la ultima orden por dispositivo: una orden nueva
    reemplaza a la anterior.
    - Una respuesta tardia todavia cuenta: si llega el estado despues del
    plazo, la orden pasa de "sin respuesta" a "confirmada" (el dispositivo
    solo era lento).
    - Un estado que no es ni el esperado ni de fallo (por ejemplo, un
    'closing' viejo mientras se pidio abrir) se ignora: la orden sigue esperando.

Seguridad entre hilos: los estados llegan desde el hilo de MQTT y las
consultas desde FastAPI, por eso todo pasa por un Lock.
"""

import itertools
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

from app import config
from app.domain.device_events import DeviceStateReport
from app.domain.order_tracking import OrderOutcome, OrderReport


@dataclass
class _TrackedOrder:
    """Orden en seguimiento (interna; se expone como OrderReport inmutable)."""

    order_id: int
    device_key: str
    requested: str
    expected_states: tuple
    failure_states: tuple
    timeout_seconds: float
    sent_monotonic: float
    sent_at: datetime
    outcome: OrderOutcome = OrderOutcome.PENDING
    reported_state: Optional[str] = None
    detail: str = ""


class OrderTracker:
    """Seguimiento en memoria, seguro entre hilos, de la ultima orden de cada dispositivo."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        """
        Args:
            clock: Reloj en segundos (se reemplaza en las pruebas por uno falso).
        """
        self._clock = clock
        self._lock = threading.Lock()
        self._orders: dict[str, _TrackedOrder] = {}
        self._ids = itertools.count(1)

    def register(
        self,
        device_key: str,
        requested: str,
        expected_states: tuple,
        failure_states: tuple,
        timeout_seconds: float,
    ) -> None:
        """Anota una orden recien enviada (reemplaza la anterior de ese dispositivo)."""
        with self._lock:
            self._orders[device_key] = _TrackedOrder(
                order_id=next(self._ids),
                device_key=device_key,
                requested=requested,
                expected_states=expected_states,
                failure_states=failure_states,
                timeout_seconds=timeout_seconds,
                sent_monotonic=self._clock(),
                sent_at=datetime.now(timezone.utc),
            )

    def on_state(self, report: DeviceStateReport) -> None:
        """Resuelve la orden del dispositivo si el estado reportado la confirma o la contradice."""
        with self._lock:
            order = self._orders.get(report.device_key)

            if order is None or order.outcome == OrderOutcome.CONFIRMED:
                return

            # Sin respuesta y mismatch todavia pueden cambiar si llega algo definitivo
            if report.state in order.expected_states:
                order.outcome = OrderOutcome.CONFIRMED
                order.detail = f"El dispositivo confirmo el estado '{report.state}'."
            elif report.state in order.failure_states:
                order.outcome = OrderOutcome.MISMATCH
                order.detail = f"El dispositivo quedo en '{report.state}' en lugar de cumplir la orden."
            else:
                return  # Estado intermedio o viejo: se sigue esperando

            order.reported_state = report.state

    def get(self, device_key: str) -> Optional[OrderReport]:
        """Ultima orden del dispositivo con su resultado actual, o None si nunca recibio una."""
        with self._lock:
            order = self._orders.get(device_key)

            if order is None:
                return None

            self._expire_if_late(order)
            return self._snapshot(order)

    def get_recent_problems(self, max_age_seconds: float) -> list[OrderReport]:
        """
        Ordenes que fallaron (sin respuesta o con estado distinto) y son recientes.

        Un problema viejo deja de mostrarse: avisar hoy de algo de hace una
        hora solo confunde.
        """
        problems: list[OrderReport] = []
        now = self._clock()

        with self._lock:
            for order in self._orders.values():
                self._expire_if_late(order)

                is_problem = order.outcome in (OrderOutcome.NO_RESPONSE, OrderOutcome.MISMATCH)
                is_recent = (now - order.sent_monotonic) <= max_age_seconds

                if is_problem and is_recent:
                    problems.append(self._snapshot(order))

        return sorted(problems, key=lambda report: report.order_id)

    # ─── Internos (se llaman con el Lock ya tomado) ──────────────────────

    def _expire_if_late(self, order: _TrackedOrder) -> None:
        """Si sigue pendiente y paso el plazo, la marca como sin respuesta."""
        if order.outcome != OrderOutcome.PENDING:
            return

        if self._clock() - order.sent_monotonic >= order.timeout_seconds:
            order.outcome = OrderOutcome.NO_RESPONSE
            order.detail = (
                f"No llego un estado nuevo en {order.timeout_seconds:g} s: "
                "el dispositivo no respondio."
            )

    @staticmethod
    def _snapshot(order: _TrackedOrder) -> OrderReport:
        return OrderReport(
            order_id=order.order_id,
            device_key=order.device_key,
            requested=order.requested,
            outcome=order.outcome,
            sent_at=order.sent_at,
            reported_state=order.reported_state,
            detail=order.detail,
        )
