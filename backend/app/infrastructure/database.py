"""
app/infrastructure/database.py

Modulo de gestion de conexion a la base de datos SQLite.

Responsabilidad: Proveer y gestionar la unica instancia de conexion
a la base de datos del sistema (patron Singleton), e inicializar
el schema si la base de datos no existe aun.

Patron Singleton:
    - Garantiza que exista una unica conexion a SQLite en todo
    el ciclo de vida de la aplicacion, evitando conflictos de
    bloqueo propios de SQLite con multiples conexiones.
"""

import sqlite3
import os
from pathlib import Path
from app.config import DATABASE_PATH

# =============================================================
# Constantes
# =============================================================
SCHEMA_FILE_PATH: str = str(
    Path(__file__).parent / "schema.sql"
)

# =============================================================
# Clase de conexion a la base de datos (Singleton)
# =============================================================
class DatabaseConnection:
    """
    Gestiona la conexion Singleton a la base de datos SQLite.
    
    Garantiza una unica instancia de conexion compartida por
    toda la aplicacion durante su ciclo de vida.
    """

    # Variable de clase que almacena la unica instancia (Singleton)
    _instance: "DatabaseConnection | None" = None
    _connection: "sqlite3.Connection | None" = None

    def __new__(cls) -> "DatabaseConnection":
        """
        Crea la instancia solo si ya no existe una anteriormente creada.
        Este es el nucleo del patron Singleton.
        
        Returns:
            La unica instancia de DatabaseConnection.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        
        return cls._instance
    
    def get_connection(self) -> sqlite3.Connection:
        """
        Retrona la conexion activa a SQLite, creandola si no existe.
        
        Returns:
            Objeto de conexion sqlite3 listo para usar

        Raises:
            RuntimeError: Si no se puede establecer la conexion a la base de datos.
        """
        if self._connection is None:
            self._connection = self._create_connection()

        return self._connection
    
    def _create_connection(self) -> sqlite3.Connection:
        """
        Crea la conexion fisica a SQLite y configura sus opciones.
        
        Returns:
            Nueva conexion sqlite3 configurada.

        Raises:
            RuntimeError: Si el archivo de schema no existe o
                si la base de datos no puede crearse.
        """
        try:
            # Crear la carpeta data/ si no existe
            os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

            connection = sqlite3.connect(
                DATABASE_PATH,
                check_same_thread=False # Permite compartir conexion entre hilos. Necesario para FastAPI (async)
            )

            # Retorna filas como diccionarios en lugar de tuplas
            connection.row_factory = sqlite3.Row

            # Activa soporte de claves foraneas. SQLite lo tiene desactivado por defecto.
            connection.execute("PRAGMA foreign_keys = ON")
            connection.commit()

            return connection
        except sqlite3.Error as error:
            raise RuntimeError(
                f"No se pudo conectar a la base de datos en '{DATABASE_PATH}': {error}"
            )

    def initialize_schema(self) -> None:
        """
        Ejecuta el archivo schema.sql para crear las tablas
        si no existen aun. Es seguro llamarlo multiples veces
        gracias al uso de CREATE TABLE IF NOT EXISTS en el schema.
        
        Raises:
            FileNotFoundError: Si schema.sql no se encuentra.
            RuntimeError: Si ocurre un error al ejecutar el schema.
        """
        if not os.path.exists(SCHEMA_FILE_PATH):
            raise FileNotFoundError(
                f"No se encontro el archivo de schema en: '{SCHEMA_FILE_PATH}'"
            )
        
        try:
            connection = self.get_connection()

            with open(SCHEMA_FILE_PATH, "r", encoding="utf-8") as schema_file:
                connection.executescript(schema_file.read())

            connection.commit()

        except sqlite3.Error as error:
            raise RuntimeError(
                f"Error al inicializar el schema de la base de datos: {error}"
            )

    def close(self) -> None:
        """
        Cierra la conexion activa a la base de datos.
        Se llama al apagar el servidor.
        """

        if self._connection is not None:
            self._connection.close()
            self._connection = None

# =============================================================
# Instancia global. El Singleton en uso
# =============================================================
db = DatabaseConnection()

def get_db() -> sqlite3.Connection:
    """
    Funcion auxiliar para inyeccion de dependencias en FastAPI.
    Los endpoints la usan para obtener la conexion sin conocer
    los detalles internos del Singleton.
    
    Returns:
        Conexion activa a SQLite.
    """
    return db.get_connection()