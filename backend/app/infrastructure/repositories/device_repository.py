"""
Repositorio SQLite para la entidad Device (luces y puertas).

Responsabilidad: Implementar las operaciones de persistencia de
dispositivos usando SQLite como motor de almacenamiento.

Patron, Repository Pattern:
    - Encapsula el acceso a datos de Device. La capa de aplicacion solo
    conoce AbstractDeviceRepository, nunca esta implementacion.

Principios SOLID aplicados:
    - D (Dependency Inversion): Implementa el contrato abstracto
    definido en domain/interfaces.py.
    - S (Single Responsibility): Solo gestiona persistencia de Device.
"""

import sqlite3
from typing import Optional

from app.domain.models import Device
from app.domain.interfaces import AbstractDeviceRepository
from app.domain.exceptions import DeviceKeyAlreadyExistsError


class SQLiteDeviceRepository(AbstractDeviceRepository):
    """
    Implementacion SQLite del repositorio de dispositivos.

    Traduce entre objetos Device del dominio y filas de la tabla devices.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        """
        Inicializa el repositorio con una conexion activa.

        Args:
            connection: Conexion SQLite activa inyectada desde fuera.
            El repositorio no crea ni cierra conexiones.
        """
        self._connection = connection

    # -------------- Metodos publicos (contrato de la interfaz) --------------

    def create(self, device: Device) -> Device:
        """
        Registra un nuevo dispositivo en la base de datos.

        Args:
            device: Instancia de Device sin ID (id=None).

        Returns:
            El mismo dispositivo con su ID asignado por SQLite.

        Raises:
            DeviceKeyAlreadyExistsError: Si el device_key ya existe.
            RuntimeError: Si ocurre otro error al insertar (por ejemplo,
            si el nodo no existe).
        """
        sql = """
            INSERT INTO devices (node_id, device_type, device_key, display_name)
            VALUES (?, ?, ?, ?)
        """

        try:
            cursor = self._connection.execute(sql, (
                device.node_id,
                device.device_type,
                device.device_key,
                device.display_name,
            ))
            self._connection.commit()
            device.id = cursor.lastrowid
            return device

        except sqlite3.IntegrityError as error:
            self._connection.rollback()

            # UNIQUE sobre device_key: El unico choque "esperado" del usuario
            if "devices.device_key" in str(error):
                raise DeviceKeyAlreadyExistsError(
                    f"Ya existe un dispositivo con el device_key '{device.device_key}'."
                )
            raise RuntimeError(f"No se pudo crear el dispositivo '{device.device_key}': {error}")

        except sqlite3.Error as error:
            self._connection.rollback()
            raise RuntimeError(f"Error al crear el dispositivo '{device.device_key}': {error}")

    def get_by_id(self, device_id: int) -> Optional[Device]:
        """
        Busca un dispositivo por su ID.

        Args:
            device_id: ID del dispositivo.

        Returns:
            El dispositivo encontrado o None si no existe.

        Raises:
            RuntimeError: Si ocurre un error al consultar la BD.
        """
        sql = "SELECT * FROM devices WHERE id = ?"

        try:
            row = self._connection.execute(sql, (device_id,)).fetchone()
            return self._row_to_device(row) if row else None

        except sqlite3.Error as error:
            raise RuntimeError(f"Error al buscar el dispositivo {device_id}: {error}")

    def get_by_key(self, device_key: str) -> Optional[Device]:
        """
        Busca un dispositivo por su device_key.

        Args:
            device_key: Identificador fijo del contrato (ej: 'light_sala').

        Returns:
            El dispositivo encontrado o None si no existe.

        Raises:
            RuntimeError: Si ocurre un error al consultar la BD.
        """
        sql = "SELECT * FROM devices WHERE device_key = ?"

        try:
            row = self._connection.execute(sql, (device_key,)).fetchone()
            return self._row_to_device(row) if row else None

        except sqlite3.Error as error:
            raise RuntimeError(f"Error al buscar el dispositivo '{device_key}': {error}")

    def get_all_by_house(
        self, house_id: int, device_type: Optional[str] = None
    ) -> list[Device]:
        """
        Retorna los dispositivos de todas las habitaciones de una casa.

        La casa se alcanza a traves del nodo (devices -> nodes -> house_id).

        Args:
            house_id: ID de la casa.
            device_type: Filtro opcional por tipo.

        Returns:
            Lista de dispositivos ordenada por tipo y nombre.

        Raises:
            RuntimeError: Si ocurre un error al consultar la BD.
        """
        sql = """
            SELECT d.* FROM devices d
            JOIN nodes n ON n.id = d.node_id
            WHERE n.house_id = ?
        """
        params: list = [house_id]

        if device_type is not None:
            sql += " AND d.device_type = ?"
            params.append(device_type)

        sql += " ORDER BY d.device_type ASC, d.display_name ASC"

        try:
            rows = self._connection.execute(sql, params).fetchall()
            return [self._row_to_device(row) for row in rows]

        except sqlite3.Error as error:
            raise RuntimeError(f"Error al obtener los dispositivos de la casa {house_id}: {error}")

    def get_all_by_node(
        self, node_id: int, device_type: Optional[str] = None
    ) -> list[Device]:
        """
        Retorna los dispositivos de una habitacion.

        Args:
            node_id: ID del nodo (habitacion).
            device_type: Filtro opcional por tipo.

        Returns:
            Lista de dispositivos ordenada por tipo y nombre.

        Raises:
            RuntimeError: Si ocurre un error al consultar la BD.
        """
        sql = "SELECT * FROM devices WHERE node_id = ?"
        params: list = [node_id]

        if device_type is not None:
            sql += " AND device_type = ?"
            params.append(device_type)

        sql += " ORDER BY device_type ASC, display_name ASC"

        try:
            rows = self._connection.execute(sql, params).fetchall()
            return [self._row_to_device(row) for row in rows]

        except sqlite3.Error as error:
            raise RuntimeError(f"Error al obtener los dispositivos del nodo {node_id}: {error}")

    def update_display_name(self, device_id: int, display_name: str) -> Optional[Device]:
        """
        Actualiza el nombre visible de un dispositivo.

        El device_key es inmutable porque el contrato MQTT depende de el.

        Args:
            device_id: ID del dispositivo.
            display_name: Nuevo nombre visible.

        Returns:
            El dispositivo actualizado o None si no existe.

        Raises:
            RuntimeError: Si ocurre un error al actualizar en la BD.
        """
        sql = """
            UPDATE devices
            SET display_name = ?, updated_at = datetime('now')
            WHERE id = ?
        """

        try:
            cursor = self._connection.execute(sql, (display_name.strip(), device_id))
            self._connection.commit()

            if cursor.rowcount == 0:
                return None

            return self.get_by_id(device_id)

        except sqlite3.Error as error:
            self._connection.rollback()
            raise RuntimeError(f"Error al actualizar el dispositivo {device_id}: {error}")

    def delete(self, device_id: int) -> bool:
        """
        Elimina un dispositivo.

        Args:
            device_id: ID del dispositivo a eliminar.

        Returns:
            True si se elimino, False si no existia.

        Raises:
            RuntimeError: Si ocurre un error al eliminar en la BD.
        """
        sql = "DELETE FROM devices WHERE id = ?"

        try:
            cursor = self._connection.execute(sql, (device_id,))
            self._connection.commit()
            return cursor.rowcount > 0

        except sqlite3.Error as error:
            self._connection.rollback()
            raise RuntimeError(f"Error al eliminar el dispositivo {device_id}: {error}")

    # -------------- Metodos privados (traduccion BD hacia dominio) --------------

    def _row_to_device(self, row: sqlite3.Row) -> Device:
        """
        Traduce una fila de SQLite a un objeto Device del dominio.

        Args:
            row: Fila de SQLite con los datos de un dispositivo.

        Returns:
            Instancia de Device construida desde la fila.
        """
        return Device(
            id=row["id"],
            node_id=row["node_id"],
            device_type=row["device_type"],
            device_key=row["device_key"],
            display_name=row["display_name"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )