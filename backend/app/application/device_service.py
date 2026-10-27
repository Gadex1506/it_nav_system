"""
Servicio de logica de negocio para los dispositivos (luces y puertas).

Responsabilidad: Orquestar las operaciones sobre dispositivos aplicando
las reglas de negocio. No conoce SQLite ni HTTP, solo coordina el
dominio y los repositorios.

Patrones aplicados:
    - Facade: Expone operaciones simples ocultando la coordinacion
    entre el repositorio de dispositivos y el de nodos.
    - Dependency Injection: Recibe los repositorios desde afuera.

Principios SOLID aplicados:
    - S: Solo contiene logica de negocio de Device.
    - D: Depende de abstracciones, no de SQLite.
"""

from typing import Optional

from app.config import VALID_DEVICE_TYPES
from app.domain.models import Device
from app.domain.interfaces import AbstractDeviceRepository, AbstractNodeRepository


class DeviceService:
    """
    Servicio que gestiona la logica de negocio de los dispositivos.

    Valida que la habitacion exista antes de registrar un dispositivo
    y centraliza las consultas que usaran el asistente y el panel.
    """

    def __init__(
        self,
        device_repository: AbstractDeviceRepository,
        node_repository: AbstractNodeRepository,
    ) -> None:
        """
        Args:
            device_repository: Repositorio de dispositivos (inyectado).
            node_repository: Repositorio de nodos, para validar la habitacion.
        """
        self._device_repository = device_repository
        self._node_repository = node_repository

    def create_device(
        self,
        node_id: int,
        device_type: str,
        device_key: str,
        display_name: str,
    ) -> Device:
        """
        Registra un dispositivo en una habitacion.

        Args:
            node_id: ID del nodo (habitacion) donde se instala.
            device_type: 'light' o 'door'.
            device_key: Identificador fijo para el contrato MQTT.
            display_name: Nombre visible del dispositivo.

        Returns:
            El dispositivo creado con su ID asignado.

        Raises:
            ValueError: Si el nodo no existe o los datos son invalidos.
            DeviceKeyAlreadyExistsError: Si el device_key ya existe.
            RuntimeError: Si ocurre un error de persistencia.
        """
        if not self._node_repository.get_by_id(node_id):
            raise ValueError(f"No existe un nodo con el ID: {node_id}.")

        device = Device.create(
            node_id=node_id,
            device_type=device_type,
            device_key=device_key,
            display_name=display_name,
        )
        return self._device_repository.create(device)

    def get_device(self, device_id: int) -> Optional[Device]:
        """
        Busca un dispositivo por su ID.

        Returns:
            El dispositivo o None si no existe.
        """
        return self._device_repository.get_by_id(device_id)

    def get_device_by_key(self, device_key: str) -> Optional[Device]:
        """
        Busca un dispositivo por su device_key (identificador del contrato).

        Returns:
            El dispositivo o None si no existe.
        """
        return self._device_repository.get_by_key(device_key.strip().lower())

    def get_devices_by_house(
        self, house_id: int, device_type: Optional[str] = None
    ) -> list[Device]:
        """
        Lista los dispositivos de una casa, opcionalmente filtrados por tipo.

        Sirve, por ejemplo, para "apaga todas las luces" (todos los 'light').

        Raises:
            ValueError: Si el tipo de dispositivo no es valido.
        """
        self._validate_type_filter(device_type)
        return self._device_repository.get_all_by_house(house_id, device_type)

    def get_devices_by_node(
        self, node_id: int, device_type: Optional[str] = None
    ) -> list[Device]:
        """
        Lista los dispositivos de una habitacion, opcionalmente por tipo.

        Sirve, por ejemplo, para "apaga la luz de la sala" (nodo + 'light').

        Raises:
            ValueError: Si el nodo no existe o el tipo no es valido.
        """
        self._validate_type_filter(device_type)

        if not self._node_repository.get_by_id(node_id):
            raise ValueError(f"No existe un nodo con el ID: {node_id}.")

        return self._device_repository.get_all_by_node(node_id, device_type)

    def rename_device(self, device_id: int, new_display_name: str) -> Device:
        """
        Cambia el nombre visible de un dispositivo.

        Raises:
            ValueError: Si el nombre esta vacio o el dispositivo no existe.
        """
        if not new_display_name or new_display_name.strip() == "":
            raise ValueError("El nombre visible del dispositivo no puede estar vacio.")

        device = self._device_repository.update_display_name(device_id, new_display_name)

        if not device:
            raise ValueError(f"No existe un dispositivo con el ID: {device_id}.")

        return device

    def delete_device(self, device_id: int) -> bool:
        """
        Elimina un dispositivo.

        Raises:
            ValueError: Si el dispositivo no existe.
        """
        if not self._device_repository.delete(device_id):
            raise ValueError(f"No existe un dispositivo con el ID: {device_id}.")

        return True

    # -------------- Metodos privados --------------

    def _validate_type_filter(self, device_type: Optional[str]) -> None:
        """
        Valida un filtro de tipo opcional.

        Raises:
            ValueError: Si se indica un tipo que no existe.
        """
        if device_type is not None and device_type not in VALID_DEVICE_TYPES:
            raise ValueError(
                f"Tipo de dispositivo invalido: '{device_type}'. "
                f"Tipos validos: {VALID_DEVICE_TYPES}"
            )