"""
app/infrastructure/gateway_provider.py

Punto unico donde se crea y se guarda la pasarela de dispositivos.

Responsabilidad: Que toda la aplicacion use UNA sola conexion MQTT y UN
solo almacen de estados, y decidir cual pasarela construir segun la
configuracion (real, o apagada).

Patrones aplicados:
    - Singleton (a nivel de modulo): una sola pasarela por proceso; abrir
    dos conexiones con el mismo client_id haria que el broker expulse a una.
    - Factory Method (_build_gateway): decide que implementacion crear.
"""

from typing import Optional

from app import config
from app.application.device_state_store import DeviceStateStore
from app.application.order_tracker import OrderTracker
from app.domain.device_events import DeviceStateReport
from app.domain.interfaces import AbstractDeviceGateway
from app.infrastructure.mqtt_device_gateway import MqttDeviceGateway
from app.infrastructure.mqtt_settings import load_mqtt_settings
from app.infrastructure.offline_device_gateway import OfflineDeviceGateway

_gateway: Optional[AbstractDeviceGateway] = None
_state_store: DeviceStateStore = DeviceStateStore()
_order_tracker: OrderTracker = OrderTracker()


def _build_gateway() -> AbstractDeviceGateway:
    """Crea la pasarela que corresponde segun la configuracion."""
    if not config.MQTT_ENABLED:
        return OfflineDeviceGateway()

    return MqttDeviceGateway(load_mqtt_settings())


def get_device_gateway() -> AbstractDeviceGateway:
    """Devuelve la pasarela unica, creandola la primera vez."""
    global _gateway

    if _gateway is None:
        _gateway = _build_gateway()

    return _gateway


def get_state_store() -> DeviceStateStore:
    """Devuelve el almacen unico de estados de dispositivos."""
    return _state_store


def get_order_tracker() -> OrderTracker:
    """Devuelve el seguimiento unico de ordenes."""
    return _order_tracker


def _handle_state_report(report: DeviceStateReport) -> None:
    """
    Reparte cada estado que llega del dispositivo a quien lo necesita.

    Patron Observer sencillo: el almacen guarda el estado y el seguimiento
    de ordenes decide si con el se cumplio la ultima orden. Se leen los
    objetos del modulo al momento de llamar (no al registrar) para que las
    pruebas puedan reemplazarlos.
    """
    _state_store.update_state(report)
    _order_tracker.on_state(report)


def start_gateway() -> None:
    """
    Conecta la pasarela y la enlaza con el almacen de estados.

    Se llama al arrancar la aplicacion. Nunca lanza error por un broker
    apagado: el backend debe poder arrancar sin la maqueta.
    """
    gateway = get_device_gateway()
    gateway.set_state_listener(_handle_state_report)
    gateway.set_availability_listener(_state_store.update_availability)
    gateway.set_board_availability_listener(_state_store.update_board_availability)
    gateway.start()


def stop_gateway() -> None:
    """Cierra la pasarela al apagar la aplicacion."""
    global _gateway

    if _gateway is not None:
        _gateway.stop()
        _gateway = None