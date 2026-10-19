"""
Lugar de la clave de desarrollador (dev_access_key.txt).

Responsabilidad: Crear, guardar y verificar la clave unica que protege las
operaciones destructivas de desarrollo (crear y eliminar casas). La clave
se genera sola la primera vez y se guarda en un archivo local que NO se
versiona (carpeta data/). Quien la necesite, la copia de ese archivo.

Principio SOLID aplicado:
    - S: Solo maneja la clave. No sabe de HTTP ni de casas.

Analogia: Es la llave de la caja fuerte. Se crea una sola vez, queda
guardada en un sitio conocido y solo quien la tenga puede abrirla.
"""

import secrets
from pathlib import Path
from typing import Optional

from app.config import DEV_KEY_FILE_PATH, DEV_KEY_BYTES


class DevKeyStore:
    """Gestiona la clave de desarrollador guardada en un archivo de texto"""

    def __init__(self, file_path: Path) -> None:
        """
        Args:
            file_path: Ruta del archivo donde se guarda la clave
        """
        self._file_path = file_path
        self._cached_key: Optional[str] = None

    @property
    def file_path(self) -> Path:
        """Ruta del archivo de la clave para mostrarla en consola"""
        return self._file_path

    def ensure_exists(self) -> tuple[str, bool]:
        """
        Garantiza que exista una clave, creandola si hace falta.

        Returns:
            Tupla (clave, fue_creada). fue_creada es True solo la
            primera vez, cuando se genero una clave nueva.

        Raises:
            RuntimeError: Si no se puede leer o escribir el archivo.
        """
        existing = self._read_key()
        if existing:
            self._cached_key = existing
            return existing, False

        new_key = secrets.token_urlsafe(DEV_KEY_BYTES)
        try:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            self._file_path.write_text(new_key, encoding="utf-8")
            self._restrict_permissions()
        except OSError as error:
            raise RuntimeError(f"No se pudo guardar la clave de desarrollador: {error}")

        self._cached_key = new_key
        return new_key, True

    def verify(self, candidate: Optional[str]) -> bool:
        """
        Comprueba si una clave recibida coincide con la guardada.

        Usa una comparacion de tiempo constante para que no se pueda
        adivinar la clave midiendo cuanto tarda la respuesta.

        Args:
            candidate: Clave recibida en la peticion (puede ser None).

        Returns:
            True solo si coincide exactamente.
        """
        if not candidate:
            return False
        key = self._cached_key or self.ensure_exists()[0]
        return secrets.compare_digest(candidate.encode("utf-8"), key.encode("utf-8"))

    # -------------- Metodos privados --------------

    def _read_key(self) -> Optional[str]:
        """Lee la clave del archivo. None si no existe o esta vacio."""
        try:
            if not self._file_path.exists():
                return None
            return self._file_path.read_text(encoding="utf-8").strip() or None
        except OSError as error:
            raise RuntimeError(f"No se pudo leer la clave de desarrollador: {error}")

    def _restrict_permissions(self) -> None:
        """Intenta dejar el archivo legible solo por el duenio (sin efecto en Windows)"""
        try:
            self._file_path.chmod(0o600)
        except OSError:
            pass


# Instancia unica usada por toda la aplicacion
dev_key_store = DevKeyStore(DEV_KEY_FILE_PATH)
