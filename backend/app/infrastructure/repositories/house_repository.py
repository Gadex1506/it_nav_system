"""
app/infrastructure/repositories/house_repository.py

Repositorio SQLite para la entidad House.

Responsabilidad: Implementar las operaciones de persistencia
de casas usando SQLite como motor de almacenamiento.

Patron - Repository Pattern:
    - Encapsula toda la logica de acceso a datos para House.
    - La capa de aplicacion solo conoce AbstractHouseRepository,
    nunca esta implementacion concreta.

Principio SOLID aplicado:
    - D (Dependency Inversion): Implementa el contrato abstracto
    definido en domain/interfaces.py.
    - S (Single Responsibility): Solo gestiona persistencia de House.
"""

import sqlite3
from typing import Optional
from datetime import datetime
from app.domain.models import House
from app.domain.interfaces import AbstractHouseRepository
from app.infrastructure.database import get_db

class SQLiteHouseRepository(AbstractHouseRepository):
    """
    Implementacion SQLite del repositorio de casas.
    
    Traduce entre objetos House del dominio y filas
    de la tabla houses en SQLite.
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

    def create(self, house: House) -> House:
        """
        Crea una nueva casa en la base de datos.
        
        Args:
            house: Instancia de House a persistir. No debe tener ID.

        Returns:
            La misma casa con su ID asinado por SQLite.

        Raises:
            RuntimeError: Si ocurre un error al insertar en la BD.
        """
        sql = """
            INSERT INTO houses (name, description)
            VALUES (?, ?)
        """

        try:
            cursor = self._connection.execute(sql, (
                house.name,
                house.description
            ))

            self._connection.commit()
            house.id = cursor.lastrowid
            return house
        
        except sqlite3.Error as error:
            self._connection.rollback()
            raise RuntimeError(f"Error al crear la casa '{house.name}': {error}")
        
    def get_by_id(self, house_id: int) -> Optional[House]:
        """
        Busca una casa por su ID.
        
        Args:
            house_id: ID de la casa a buscar.

        Returns:
            La casa encontrada o None si no existe.

        Raises:
            RuntimeError: Si ocurre un error al consultar la BD.
        """
        sql = "SELECT * FROM houses WHERE id = ?"

        try:
            cursor = self._connection.execute(sql, (house_id,))
            row = cursor.fetchone()
            return self._row_to_house(row) if row else None
        
        except sqlite3.Error as error:
            raise RuntimeError(f"Error al buscar la casa por su ID {house_id}: {error}")
        
    def get_all(self) -> list[House]:
        """
        Retorna todas las casas registradas en la base de datos ordenadas por nombre.
        
        Returns:
            Lista de casas. Lista vacia si no hay ninguna casa registrada

        Raises:
            RuntimeError: Si ocurre un error al consultar la BD.
        """
        sql = "SELECT * FROM houses ORDER BY name ASC"

        try:
            cursor = self._connection.execute(sql)
            rows = cursor.fetchall()
            return [self._row_to_house(row) for row in rows]
        
        except sqlite3.Error as error:
            raise RuntimeError(f"Error al obtener la lista de casas registradas: {error}")


    # -------------- Metodos privados (traduccion BD -> dominio) --------------

    def _row_to_house(self, row: sqlite3.Row) -> House:
        """
        Traduce una fila de SQLite a un objeto House del dominio.
        
        Este metodo es el traductor entre el mundo relacional
        y el mundo de objetos. Solo se usa internamente.

        Args:
            row: Fila de SQLite con los datos de una casa.

        Returns:
            Instancia de House construida desde la fila.
        """
        return House(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )

