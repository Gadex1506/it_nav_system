"""
Dependencias de seguridad para los endpoints de desarrollo.

Responsabilidad: Exigir la clave de desarrollador (cabecera X-Dev-Key)
en las operaciones destructivas. FastAPI la muestra en /docs como un
boton "Authorize", asi tambien se puede probar desde Swagger (Interfaz de FAST API).

Patron: Dependency Injection (se usa con Depends en cada endpoint).
"""

from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import DEV_KEY_HEADER_NAME
from app.infrastructure.dev_key_store import dev_key_store

_api_key_header = APIKeyHeader(
    name=DEV_KEY_HEADER_NAME,
    auto_error=False,
    description="Clave de desarrollador (contenido de data/dev_access_key.txt)",
)


def require_dev_key(provided_key: Optional[str] = Security(_api_key_header)) -> None:
    """
    Deja pasar la peticion solo si trae la clave de desarrollador correcta.

    Raises:
        HTTPException 401: Si la clave falta o es incorrecta.
    """
    if not dev_key_store.verify(provided_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clave de desarrollador ausente o incorrecta.",
        )
