"""
Configuracion compartida de pytest para los tests de integracion.

Responsabilidad: Proveer un cliente de pruebas (TestClient) que
usa una base de datos SQLite temporal y aislada, distinta a la
base de datos real del sistema. Cada test arranca con datos limpios.

Patron de disenio aplicado:
    - Test Fixture: Prepara el entorno necesario (DB temporal + cliente
    HTTP) antes de cada test y lo limpia despues, sin que cada test
    tenga que repetir esa configuración.

Principio SOLID aplicado:
    - D (Dependency Inversion): Sustituimos la base de datos real por
    una temporal sin tocar ni una linea del codigo de produccion,
    gracias a que todo el sistema depende de get_db() como abstracción.
"""

import os;
import pytest
from fastapi.testclient import TestClient

@pytest.fixture()
def client(tmp_path, monkeypatch):
    """
    Crea un cliente de pruebas conectado a una base de datos temporal.

    Antes de cada test que use este fixture:
        1. Crea una ruta de archivo temporal para la DB (tmp_path la 
        provee pytest automaticamente y la borra sola al finalizar).
        2. Redirige la constante DATABASE_PATH hacia esa ruta temporal.
        3. Resetea la conexion Singleton para forzar que se conecte
        a la nueva base de datos temporal, no a la real.
        4. Crea una casa base para que ACTIVE_HOUSE_ID=1 sea valido.
    
    Args:
        tmp_path: Fixture nativo de pytest, carpeta temporal unica
            por test que se elimina automaticamente al finalizar.
        monkeypatch: Fixture nativo de pytest para sustituir valores
            de modulos temporalmente, solo durante el test.

    Yields:
        TestClient listo para hacer requests HTTP simulados.
    """
    test_db_path = str(tmp_path / "test_navigation.db")

    # Redirige el path de la base de datos SOLO durante este test
    monkeypatch.setattr(
        "app.infrastructure.database.DATABASE_PATH",
        test_db_path
    )

    # Fuerza que el Singleton olvide la conexion anterior (si existia)
    # para que la proxima vez que algo pida una conexion, se cree
    # una nueva apuntando a la base de datos temporal
    from app.infrastructure.database import db
    db._connection = None

    from app.main import app as fastapi_app

    # El "with" activa el lifespan de FastAPI: crea el schema
    # automaticamente en la base de datos temporal al iniciar.
    with TestClient(fastapi_app) as test_client:
        # Toda instalacion necesita al menos una casa activa.
        # la creamos aqui para que ACTIVE_HOUSE_ID=1 sea valido
        # en todos los tests que usen este fixture.
        response = test_client.post(
            "/dev/houses",
            json={"name": "Casa de Prueba", "description": "Entorno de testing"}
        )
        assert response.status_code == 201, "No se pudo crear la casa de pruebas."

    yield test_client

    # ----- Limpieza despues del test ------------------------------------------
    db.close()

