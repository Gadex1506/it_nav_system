"""
app/infrastructure/mqtt_device_gateway.py

Pasarela real hacia luces y puertas usando MQTT (libreria paho-mqtt).

Responsabilidad: Mantener la conexion con el broker, publicar las
ordenes del backend y entregar al resto del sistema lo que los ESP32
cuentan (estado y disponibilidad). No decide NADA de negocio.

Decisiones importantes:
    - Si el broker esta apagado el backend arranca igual: paho reintenta
    solo, con esperas crecientes. Unity debe seguir funcionando sin la maqueta.
    - Si no hay conexion, las ordenes se RECHAZAN, no se encolan: una
    orden "enciende la luz" que llegue 5 minutos tarde seria peor que un error.
    - Las suscripciones se rehacen en cada reconexion (sesion limpia).
    - Un error al procesar un mensaje nunca debe matar el hilo de red.

Patron aplicado:
    - Adapter: traduce la interfaz AbstractDeviceGateway al API de paho.
"""

import logging
import threading
from typing import Optional

import paho.mqtt.client as mqtt

from app.domain.exceptions import GatewayUnavailableError
from app.domain.interfaces import (
    AbstractDeviceGateway,
    AvailabilityListener,
    BoardAvailabilityListener,
    StateListener,
)
from app.infrastructure import mqtt_protocol
from app.infrastructure.mqtt_settings import MqttSettings

logger = logging.getLogger(__name__)


class MqttDeviceGateway(AbstractDeviceGateway):
    """
    Implementacion MQTT de la pasarela de dispositivos.

    paho corre su propio hilo de red (loop_start); los callbacks se
    ejecutan en ese hilo, por eso los oyentes que se registren
    deben ser seguros para varios hilos (el DeviceStateStore lo es).
    """

    def __init__(self, settings: MqttSettings) -> None:
        """
        Args:
            settings: Datos de conexion al broker.
        """
        self._settings = settings
        self._connected = threading.Event()
        self._state_listener: Optional[StateListener] = None
        self._availability_listener: Optional[AvailabilityListener] = None
        self._board_listener: Optional[BoardAvailabilityListener] = None

        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=settings.client_id,
            protocol=mqtt.MQTTv311,
        )
        self._client.username_pw_set(settings.username, settings.password)
        self._client.reconnect_delay_set(
            min_delay=settings.reconnect_min_seconds,
            max_delay=settings.reconnect_max_seconds,
        )
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    # ─── Ciclo de vida ───────────────────────────────────────────────────

    def start(self) -> None:
        """Programa la conexion y arranca el hilo de red (no bloquea)."""
        try:
            self._client.connect_async(
                self._settings.host,
                self._settings.port,
                self._settings.keepalive_seconds,
            )
            self._client.loop_start()
            logger.info(
                "Pasarela MQTT iniciada; conectando a %s:%s",
                self._settings.host, self._settings.port,
            )
        except Exception as error:
            # Cualquier fallo aqui no debe impedir que el backend arranque
            logger.error("No se pudo iniciar la pasarela MQTT: %s", error)

    def stop(self) -> None:
        """Cierra la conexion y detiene el hilo de red."""
        try:
            self._client.disconnect()
            self._client.loop_stop()
        except Exception as error:
            logger.error("Error al detener la pasarela MQTT: %s", error)
        finally:
            self._connected.clear()

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    # ─── Ordenes (backend -> ESP32) ──────────────────────────────────────

    def publish_light_command(self, device_key: str, state: str) -> None:
        self._publish_order(
            mqtt_protocol.light_set_topic(device_key),
            mqtt_protocol.encode_light_command(state),
            device_key,
        )

    def publish_door_command(self, device_key: str, action: str, hold_ms: Optional[int] = None) -> None:
        self._publish_order(
            mqtt_protocol.door_set_topic(device_key),
            mqtt_protocol.encode_door_command(action, hold_ms),
            device_key,
        )

    def _publish_order(self, topic: str, payload: bytes, device_key: str) -> None:
        """Publica una orden (comun a luces y puertas)."""
        if not self.is_connected:
            raise GatewayUnavailableError(
                "No hay conexion con el broker MQTT; la orden no se envio."
            )

        result = self._client.publish(
            topic,
            payload,
            qos=self._settings.qos,
            retain=False,  # una orden vieja no debe repetirse al reconectar
        )

        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise GatewayUnavailableError(
                f"El broker rechazo la orden para '{device_key}' (codigo {result.rc})."
            )

    # ─── Oyentes (ESP32 -> backend) ──────────────────────────────────────

    def set_state_listener(self, listener: StateListener) -> None:
        self._state_listener = listener

    def set_availability_listener(self, listener: AvailabilityListener) -> None:
        self._availability_listener = listener

    def set_board_availability_listener(self, listener: BoardAvailabilityListener) -> None:
        self._board_listener = listener

    # ─── Callbacks de paho (se ejecutan en el hilo de red) ───────────────

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code.is_failure:
            logger.error("El broker rechazo la conexion: %s", reason_code)
            return

        self._connected.set()
        logger.info("Conectado al broker MQTT.")

        # Se suscribe en cada conexion: con sesion limpia el broker olvida todo
        client.subscribe([
            (mqtt_protocol.state_subscription_topic(), self._settings.qos),
            (mqtt_protocol.availability_subscription_topic(), self._settings.qos),
            (mqtt_protocol.board_availability_subscription_topic(), self._settings.qos),
        ])

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties) -> None:
        self._connected.clear()

        if reason_code.is_failure:
            logger.warning("Desconectado del broker MQTT (%s). Se reintentara solo.", reason_code)
        else:
            logger.info("Conexion con el broker MQTT cerrada.")

    def _on_message(self, client, userdata, message) -> None:
        try:
            self._dispatch(message.topic, message.payload)
        except Exception:
            # Nunca dejar que un mensaje raro mate el hilo de red
            logger.exception("Error procesando el mensaje del tema '%s'.", message.topic)

    def _dispatch(self, topic: str, payload: bytes) -> None:
        """Interpreta un mensaje recibido y avisa al oyente correspondiente."""
        board = mqtt_protocol.parse_board_topic(topic)

        if board is not None:
            self._dispatch_board(board, payload)
            return

        parsed = mqtt_protocol.parse_device_topic(topic)

        if parsed is None:
            logger.warning("Tema ignorado: '%s'.", topic)
            return

        device_key, topic_kind = parsed

        if topic_kind == mqtt_protocol.TOPIC_STATE and self._state_listener:
            report = mqtt_protocol.decode_state_payload(device_key, payload)
            if report is not None:
                self._state_listener(report)

        elif topic_kind == mqtt_protocol.TOPIC_AVAILABILITY and self._availability_listener:
            report = mqtt_protocol.decode_availability_payload(device_key, payload)
            if report is not None:
                self._availability_listener(report)

    def _dispatch_board(self, board: tuple[str, str], payload: bytes) -> None:
        """Atiende los mensajes de una placa (por ahora solo su disponibilidad)."""
        board_id, topic_kind = board

        if topic_kind != mqtt_protocol.TOPIC_AVAILABILITY or not self._board_listener:
            return

        report = mqtt_protocol.decode_board_availability_payload(board_id, payload)
        if report is not None:
            self._board_listener(report)