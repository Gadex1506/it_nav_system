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
from dotenv import load_dotenv
from fastapi.testclient import TestClient

# Domain
from app.domain.interfaces import AbstractDeviceGateway

load_dotenv()

class FakeDeviceGateway(AbstractDeviceGateway):
    """
    Pasarela falsa para pruebas: guarda en una lista lo que se le pide
    publicar y permite simular lo que contaria un ESP32. Asi las pruebas
    no necesitan un broker MQTT real.
    """

    def __init__(self, connected: bool = True) -> None:
        self.connected = connected
        self.published: list[tuple[str, str]] = []
        self.published_doors: list = []
        self.started = False
        self.stopped = False
        self._state_listener = None
        self._availability_listener = None
        self._board_listener = None

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    @property
    def is_connected(self) -> bool:
        return self.connected

    def publish_light_command(self, device_key: str, state: str) -> None:
        from app.domain.exceptions import GatewayUnavailableError
        if not self.connected:
            raise GatewayUnavailableError("Sin conexion (pasarela falsa).")
        self.published.append((device_key, state))

    def publish_door_command(self, device_key: str, action: str, hold_ms=None) -> None:
        from app.domain.exceptions import GatewayUnavailableError
        if not self.connected:
            raise GatewayUnavailableError("Sin conexion (pasarela falsa).")
        self.published_doors.append((device_key, action, hold_ms))

    def set_state_listener(self, listener) -> None:
        self._state_listener = listener

    def set_availability_listener(self, listener) -> None:
        self._availability_listener = listener

    def set_board_availability_listener(self, listener) -> None:
            self._board_listener = listener

    # --- Ayudas de prueba: simulan al ESP32 ---
    def emit_state(self, report) -> None:
        self._state_listener(report)

    def emit_availability(self, report) -> None:
        self._availability_listener(report)

    def emit_board_availability(self, report) -> None:
        self._board_listener(report)


@pytest.fixture()
def fake_gateway(monkeypatch):
    """
    Reemplaza la pasarela real por una falsa y reinicia el almacen de
    estados, para que ningun test toque un broker MQTT de verdad.
    """
    from app.application.device_state_store import DeviceStateStore
    from app.infrastructure import gateway_provider
    from app.application.order_tracker import OrderTracker

    fake = FakeDeviceGateway()
    monkeypatch.setattr(gateway_provider, "_gateway", fake)
    monkeypatch.setattr(gateway_provider, "_state_store", DeviceStateStore())
    monkeypatch.setattr(gateway_provider, "_order_tracker", OrderTracker())
    return fake

@pytest.fixture()
def client(tmp_path, monkeypatch, fake_gateway):
    """
    Crea un cliente de pruebas conectado a una base de datos temporal.

    Antes de cada test que use este fixture:
        1. Crea una ruta de archivo temporal para la DB (tmp_path la 
        provee pytest automaticamente y la borra sola al finalizar).
        2. Redirige la constante DATABASE_PATH hacia esa ruta temporal.
        3. Resetea la conexion Singleton para forzar que se conecte
        a la nueva base de datos temporal, no a la real.
    
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

    # Clave de desarrollador temporal: nunca se toca la clave real
    from app.infrastructure.dev_key_store import dev_key_store
    test_dev_key = "clave-de-prueba-solo-para-tests-0123456789"
    monkeypatch.setattr(dev_key_store, "_key", test_dev_key)

    from app.main import app as fastapi_app

    # El "with" activa el lifespan de FastAPI: crea el schema
    # automaticamente en la base de datos temporal al iniciar.
    with TestClient(fastapi_app) as test_client:
        # Toda instalacion necesita al menos una casa activa.
        response = test_client.post(
            "/dev/houses",
            json={"name": "Casa de Prueba", "description": "Entorno de testing"},
            headers={"X-Dev-Key": test_dev_key}
        )
        assert response.status_code == 201, "No se pudo crear la casa de pruebas."
        test_client.headers.update({"X-Dev-Key": test_dev_key})
        yield test_client

    # ----- Limpieza despues del test ------------------------------------------
    db.close()