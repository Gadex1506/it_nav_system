"""
app/infrastructure/dev_key_store.py

Guardian de la clave de desarrollador.

Responsabilidad: Verificar la clave unica que protege las operaciones de
desarrollo (crear/eliminar casas y dispositivos, ordenes directas al
gateway). La clave YA NO se genera sola: viene del archivo .env
(variable INCLUSIVE_DEV_KEY), asi todo el equipo usa la misma y nadie
obtiene acceso solo por levantar el backend.

Principio SOLID aplicado:
    - S: Solo guarda y compara la clave. No sabe de HTTP ni de casas.

Analogia: antes cada persona que abria la caja fuerte se fabricaba su
propia llave; ahora hay una sola llave y quien la quiera debe pedirsela
al duenio (el .env que se comparte por un canal privado).
"""

import logging
import secrets
from typing import Optional

from app.config import DEV_ACCESS_KEY, DEV_KEY_ENV_NAME, DEV_KEY_MIN_LENGTH

logger = logging.getLogger(__name__)


class DevKeyStore:
    """Compara claves recibidas contra la clave de desarrollador configurada."""

    def __init__(self, key: str) -> None:
        """
        Args:
            key: Clave leida del .env (texto vacio si no existe).
        """
        self._key = key

    @property
    def is_configured(self) -> bool:
        """True si hay una clave con la longitud minima exigida."""
        return len(self._key) >= DEV_KEY_MIN_LENGTH

    def log_status(self) -> None:
        """Avisa en consola, al arrancar, si la clave falta o es debil."""
        if self.is_configured:
            logger.info("Clave de desarrollador cargada desde el .env.")
        else:
            logger.warning(
                "%s no esta definida o tiene menos de %d caracteres en el .env: "
                "los endpoints /dev protegidos responderan 503 hasta configurarla.",
                DEV_KEY_ENV_NAME, DEV_KEY_MIN_LENGTH,
            )

    def verify(self, candidate: Optional[str]) -> bool:
        """
        Comprueba si una clave recibida coincide con la configurada.

        Usa comparacion de tiempo constante para que no se pueda adivinar
        la clave midiendo cuanto tarda la respuesta.

        Returns:
            True solo si hay clave configurada y coincide exactamente.
        """
        if not candidate or not self.is_configured:
            return False
        return secrets.compare_digest(candidate.encode("utf-8"), self._key.encode("utf-8"))


# Instancia unica usada por toda la aplicacion
dev_key_store = DevKeyStore(DEV_ACCESS_KEY)
