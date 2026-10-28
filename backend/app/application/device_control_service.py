"""
app/application/device_control_service.py

Servicio que da ordenes a los dispositivos fisicos (luces y puertas) y consulta su estado.

Responsabilidad: Aplicar las reglas antes de enviar una orden (el
dispositivo existe, es del tipo correcto, el estado o la accion son validos) y delegar el envio
a la pasarela. No sabe nada de MQTT ni de HTTP.

La orden es ASINCRONA: set_light() y set_door() solo confirman que la orden salio.
Que la luz realmente cambio lo dira el ESP32 publicando su estado, que
se consulta con get_live_status(). Analogia: dejar una nota en la puerta
del vecino; sabes que la dejaste, no que ya la leyo.

Patrones aplicados:
    - Facade: una operacion simple que coordina repositorio, pasarela y estado.
    - Dependency Injection: todo llega por el constructor.
"""

from typing import Optional

from app.config import (
    DEVICE_TYPE_DOOR,
    DEVICE_TYPE_LIGHT,
    DOOR_ACTION_OPEN,
    DOOR_HOLD_MS_MAX,
    DOOR_HOLD_MS_MIN,
    VALID_DOOR_ACTIONS,
    VALID_LIGHT_STATES,
)
from app.application.device_service import DeviceService
from app.application.device_state_store import DeviceLiveStatus, DeviceStateStore
from app.domain.exceptions import DeviceNotFoundError, GatewayUnavailableError
from app.domain.interfaces import AbstractDeviceGateway
from app.domain.models import Device


class DeviceControlService:
    """Da ordenes a las luces y puertas y consulta su ultimo estado conocido."""

    def __init__(
        self,
        device_service: DeviceService,
        gateway: AbstractDeviceGateway,
        state_store: DeviceStateStore,
    ) -> None:
        """
        Args:
            device_service: Para buscar dispositivos por su device_key.
            gateway: Pasarela por la que salen las ordenes.
            state_store: Memoria con el ultimo estado conocido.
        """
        self._device_service = device_service
        self._gateway = gateway
        self._state_store = state_store

    @property
    def gateway_connected(self) -> bool:
        """True si ahora mismo se pueden enviar ordenes."""
        return self._gateway.is_connected

    def set_light(self, device_key: str, state: str) -> Device:
        """
        Pide encender o apagar una luz.

        Args:
            device_key: Identificador de la luz (ej: 'light_sala').
            state: 'on' u 'off'.

        Returns:
            El dispositivo al que se le envio la orden.

        Raises:
            ValueError: Si el estado no es valido o el dispositivo no es una luz.
            DeviceNotFoundError: Si no existe un dispositivo con ese device_key.
            GatewayUnavailableError: Si no se pudo enviar (broker apagado).
        """
        normalized_state = self._normalize_state(state)
        device = self._get_device(device_key, DEVICE_TYPE_LIGHT, "una luz")

        self._gateway.publish_light_command(device.device_key, normalized_state)
        return device

    def set_door(self, device_key: str, action: str, hold_ms: Optional[int] = None) -> Device:
        """
        Pide abrir o cerrar una puerta.

        Args:
            device_key: Identificador de la puerta (ej: 'door_cuarto_principal').
            action: 'open' o 'close'.
            hold_ms: Cierre de seguridad en ms (solo con 'open'). Si se omite,
                el ESP32 usa su valor por defecto.

        Returns:
            El dispositivo al que se le envio la orden.

        Raises:
            ValueError: Si la accion o hold_ms no son validos, o el dispositivo no es una puerta.
            DeviceNotFoundError: Si no existe un dispositivo con ese device_key.
            GatewayUnavailableError: Si no se pudo enviar (broker apagado).
        """
        normalized_action = self._normalize_door_action(action)
        self._validate_hold_ms(normalized_action, hold_ms)
        device = self._get_device(device_key, DEVICE_TYPE_DOOR, "una puerta")

        self._gateway.publish_door_command(device.device_key, normalized_action, hold_ms)
        return device

    def set_all_lights(self, house_id: int, state: str) -> list[str]:
        """
        Pide encender o apagar TODAS las luces de una casa.

        Es lo que usara "apaga todas las luces". Si no hay conexion falla
        antes de enviar nada, para no dejar la casa a medias.

        Returns:
            Los device_key a los que se envio la orden (vacio si no hay luces).

        Raises:
            ValueError: Si el estado no es valido.
            GatewayUnavailableError: Si no hay conexion con el broker.
        """
        normalized_state = self._normalize_state(state)
        lights = self._device_service.get_devices_by_house(house_id, DEVICE_TYPE_LIGHT)

        if lights and not self._gateway.is_connected:
            raise GatewayUnavailableError(
                "No hay conexion con el broker MQTT; no se envio ninguna orden."
            )

        for light in lights:
            self._gateway.publish_light_command(light.device_key, normalized_state)

        return [light.device_key for light in lights]

    def get_live_status(self, device_key: str) -> Optional[DeviceLiveStatus]:
        """Ultimo estado conocido de un dispositivo, o None si nunca reporto."""
        return self._state_store.get(device_key.strip().lower())

    def get_all_live_status(self) -> list[DeviceLiveStatus]:
        """Ultimo estado conocido de todos los dispositivos que han reportado."""
        return self._state_store.get_all()

    # ─── Utilidades internas ─────────────────────────────────────────────

    @staticmethod
    def _normalize_state(state: str) -> str:
        normalized = (state or "").strip().lower()

        if normalized not in VALID_LIGHT_STATES:
            raise ValueError(
                f"Estado invalido '{state}'. Valores permitidos: {', '.join(VALID_LIGHT_STATES)}."
            )

        return normalized

    @staticmethod
    def _normalize_door_action(action: str) -> str:
        normalized = (action or "").strip().lower()

        if normalized not in VALID_DOOR_ACTIONS:
            raise ValueError(
                f"Accion invalida '{action}'. Valores permitidos: {', '.join(VALID_DOOR_ACTIONS)}."
            )

        return normalized

    @staticmethod
    def _validate_hold_ms(action: str, hold_ms: Optional[int]) -> None:
        """hold_ms solo tiene sentido al abrir y debe estar en un rango razonable."""
        if hold_ms is None:
            return

        if action != DOOR_ACTION_OPEN:
            raise ValueError("hold_ms solo se puede usar con la accion 'open'.")

        if not DOOR_HOLD_MS_MIN <= hold_ms <= DOOR_HOLD_MS_MAX:
            raise ValueError(
                f"hold_ms debe estar entre {DOOR_HOLD_MS_MIN} y {DOOR_HOLD_MS_MAX} milisegundos."
            )

    def _get_device(self, device_key: str, expected_type: str, type_label: str) -> Device:
        """Busca un dispositivo y comprueba que sea del tipo esperado."""
        device = self._device_service.get_device_by_key(device_key or "")

        if device is None:
            raise DeviceNotFoundError(f"No existe un dispositivo con la clave '{device_key}'.")

        if device.device_type != expected_type:
            raise ValueError(f"El dispositivo '{device_key}' no es {type_label}.")

        return device