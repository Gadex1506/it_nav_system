"""
simulator/devices.py

Placa ESP32 simulada y los dispositivos que maneja.

Dos piezas, igual que en la realidad:
    - SimulatedBoard: la PLACA. Tiene UNA conexion MQTT, UN Last Will y
    maneja varios dispositivos (luces y, luego, puertas).
    - SimulatedDevice: la LOGICA de un dispositivo (que estado tiene y
    como reacciona a una orden). No sabe nada de MQTT.

Por que una sola conexion por placa: una conexion MQTT solo puede tener
un Last Will. Si la placa se cae, el broker avisa "offline" POR LA PLACA
(contrato v0.3) y el backend entiende que todos sus dispositivos caen.

Las luces reaccionan al instante. Las puertas (servo) tardan en moverse y
publican estados intermedios (opening, closing) por su cuenta, con
temporizadores; por eso cada dispositivo recibe de la placa una funcion
para publicar (bind).

Patron aplicado:
    - Template Method: SimulatedDevice define los dos pasos que cada tipo
    de dispositivo rellena (estado actual y reaccion a una orden).
    Analogia: la receta base de "electrodomestico"; la luz y la puerta solo
    cambian lo que hacen al recibir la orden.
    - Composite sencillo: la placa contiene dispositivos y les reparte
    las ordenes segun el tema en el que llegan.
"""

import logging
import queue
import threading
import time
from abc import ABC, abstractmethod
from typing import Callable, Optional

import paho.mqtt.client as mqtt

from simulator import contract
from simulator.settings import (
    GRACEFUL_STOP_WAIT_SECONDS,
    KEEPALIVE_SECONDS,
    MS_PER_SECOND,
    RECONNECT_MAX_SECONDS,
    RECONNECT_MIN_SECONDS,
    SimulatorSettings,
)

logger = logging.getLogger(__name__)

QOS = 1
CLIENT_ID_PREFIX = "sim-esp32-"   # Distinto de 'esp32-casa' (placa real) para no expulsarla


class SimulatedDevice(ABC):
    """Logica de un dispositivo fisico. No habla MQTT: eso lo hace la placa."""

    def __init__(self, device_key: str) -> None:
        """
        Args:
            device_key: Identificador fijo del dispositivo (ej: 'light_sala').
        """
        self.device_key = device_key
        self._publish: Optional[Callable[[str, str], None]] = None

    def bind(self, publish: Callable[[str, str], None]) -> None:
        """
        La placa le entrega la funcion para publicar estados.

        Solo la usan los dispositivos que cambian de estado por su cuenta
        (la puerta, que pasa de 'opening' a 'open' sin que nadie lo pida).
        """
        self._publish = publish

    def shutdown(self) -> None:
        """Se llama cuando la placa se apaga o se cae. Por defecto no hay nada que detener."""
        return None

    @abstractmethod
    def current_state(self) -> str:
        """Estado actual del dispositivo (ej: 'off')."""
        ...

    @abstractmethod
    def handle_command(self, payload: bytes) -> Optional[str]:
        """
        Reacciona a una orden.

        Returns:
            El nuevo estado a publicar, o None si la orden se ignora.
        """
        ...


class SimulatedLight(SimulatedDevice):
    """Luz simulada: solo puede estar encendida u apagada."""

    def __init__(self, device_key: str) -> None:
        super().__init__(device_key)
        self._state = contract.STATE_OFF

    def current_state(self) -> str:
        return self._state

    def handle_command(self, payload: bytes) -> Optional[str]:
        command = contract.parse_light_command(payload)

        if command is None:
            return None

        self._state = command
        return self._state


class SimulatedDoor(SimulatedDevice):
    """
    Puerta con servo simulada (contrato v0.3).

    Estados: closed -> opening -> open -> closing -> closed.
    El servo tarda travel_seconds en moverse. Si no llega 'close', la
    puerta se cierra sola al vencer hold_ms (el cierre de seguridad).

    Cada orden nueva invalida los temporizadores anteriores mediante un
    contador (_token): un temporizador viejo que despierta tarde ve que su
    numero ya no coincide y no hace nada. Analogia: el numero del turno en
    una fila; si ya llamaron a otro, el tuyo ya no vale.
    """

    def __init__(self, device_key: str, travel_seconds: float, default_hold_seconds: float) -> None:
        """
        Args:
            device_key: Identificador fijo de la puerta (ej: 'door_banio').
            travel_seconds: Lo que tarda el servo en abrir o cerrar.
            default_hold_seconds: Cierre de seguridad si la orden no trae hold_ms.
        """
        super().__init__(device_key)
        self._travel = travel_seconds
        self._default_hold = default_hold_seconds
        self._lock = threading.Lock()
        self._state = contract.DOOR_CLOSED
        self._token = 0
        self._timers: list[threading.Timer] = []

    def current_state(self) -> str:
        with self._lock:
            return self._state

    def handle_command(self, payload: bytes) -> Optional[str]:
        command = contract.parse_door_command(payload)

        if command is None:
            return None

        with self._lock:
            self._invalidate_timers()
            token = self._token

            if command.action == contract.ACTION_OPEN:
                hold = (command.hold_ms / MS_PER_SECOND) if command.hold_ms else self._default_hold

                if self._state == contract.DOOR_OPEN:
                    # Ya estaba abierta: se reinicia la cuenta del cierre de seguridad
                    self._schedule(hold, self._on_hold_expired, token)
                    return self._state

                self._state = contract.DOOR_OPENING
                self._schedule(self._travel, self._finish_open, token, hold)
                return self._state

            # close: tiene prioridad sobre cualquier cierre automatico pendiente
            if self._state == contract.DOOR_CLOSED:
                return self._state

            self._state = contract.DOOR_CLOSING
            self._schedule(self._travel, self._finish_close, token)
            return self._state

    def shutdown(self) -> None:
        with self._lock:
            self._invalidate_timers()

    # ─── Pasos automaticos (se ejecutan en hilos de temporizador) ────────

    def _finish_open(self, token: int, hold_seconds: float) -> None:
        with self._lock:
            if token != self._token:
                return
            self._state = contract.DOOR_OPEN
            self._schedule(hold_seconds, self._on_hold_expired, token)
        self._announce(contract.DOOR_OPEN)

    def _on_hold_expired(self, token: int) -> None:
        with self._lock:
            if token != self._token:
                return
            logger.info("[%s] Vencio hold_ms: cierre de seguridad.", self.device_key)
            self._state = contract.DOOR_CLOSING
            self._schedule(self._travel, self._finish_close, token)
        self._announce(contract.DOOR_CLOSING)

    def _finish_close(self, token: int) -> None:
        with self._lock:
            if token != self._token:
                return
            self._state = contract.DOOR_CLOSED
        self._announce(contract.DOOR_CLOSED)

    # ─── Internos ────────────────────────────────────────────────────────

    def _schedule(self, delay_seconds: float, action: Callable, *args) -> None:
        """Programa un paso automatico. Se llama con el Lock ya tomado."""
        timer = threading.Timer(delay_seconds, action, args=args)
        timer.daemon = True
        self._timers.append(timer)
        timer.start()

    def _invalidate_timers(self) -> None:
        """Cancela lo pendiente y anula los temporizadores que ya estan despertando."""
        self._token += 1
        for timer in self._timers:
            timer.cancel()
        self._timers.clear()

    def _announce(self, state: str) -> None:
        if self._publish is not None:
            logger.info("[%s] Estado -> %s", self.device_key, state)
            self._publish(self.device_key, state)


class SimulatedBoard:
    """Una placa ESP32 simulada con su unica conexion MQTT y sus dispositivos."""

    def __init__(
        self,
        board_id: str,
        devices: list[SimulatedDevice],
        settings: SimulatorSettings,
    ) -> None:
        """
        Args:
            board_id: Identificador de la placa (ej: 'casa').
            devices: Dispositivos que maneja esta placa.
            settings: Datos de conexion y latencia simulada.
        """
        self.board_id = board_id
        self._devices = {device.device_key: device for device in devices}
        for device in devices:
            device.bind(self._publish_state)
        self._settings = settings
        self._started_at = time.monotonic()
        self._commands: queue.Queue = queue.Queue()
        self._worker = threading.Thread(target=self._process_commands, daemon=True)
        self._availability_topic = contract.board_availability_topic(board_id)

        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"{CLIENT_ID_PREFIX}{board_id}",
            protocol=mqtt.MQTTv311,
        )
        self._client.username_pw_set(settings.username, settings.password)
        # Last Will UNICO de la placa: si cae sin avisar, el broker publica 'offline'
        self._client.will_set(
            self._availability_topic,
            contract.AVAILABILITY_OFFLINE,
            qos=QOS,
            retain=True,
        )
        self._client.reconnect_delay_set(RECONNECT_MIN_SECONDS, RECONNECT_MAX_SECONDS)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

    # ─── Ciclo de vida ───────────────────────────────────────────────────

    def start(self) -> None:
        """Conecta (sin bloquear; reintenta solo si el broker no esta)."""
        self._worker.start()
        self._client.connect_async(self._settings.host, self._settings.port, KEEPALIVE_SECONDS)
        self._client.loop_start()

    def stop(self) -> None:
        """
        Apagado ORDENADO: la placa avisa 'offline' y se desconecta.

        Es lo contrario de una caida: aqui la placa se despide.
        Para simular un corte de energia basta con terminar el proceso
        sin llamar a stop(); el broker publicara el Last Will.
        """
        try:
            info = self._client.publish(
                self._availability_topic, contract.AVAILABILITY_OFFLINE, qos=QOS, retain=True
            )
            info.wait_for_publish(timeout=GRACEFUL_STOP_WAIT_SECONDS)
        except Exception as error:
            logger.warning("[%s] No se pudo avisar 'offline': %s", self.board_id, error)

        self._shutdown_devices()
        self._commands.put(None)  # Centinela: detiene el hilo de trabajo
        self._client.disconnect()
        self._client.loop_stop()

    def simulate_power_cut(self) -> None:
        """
        Corte de energia: cierra el socket SIN despedirse.

        Sirve para probar el Last Will dentro de un mismo proceso
        (en la linea de comandos basta con Ctrl+C).
        """
        self._shutdown_devices()
        self._commands.put(None)
        self._client.loop_stop()
        sock = self._client.socket()
        if sock is not None:
            sock.close()

    def _shutdown_devices(self) -> None:
        """Detiene los temporizadores de los dispositivos (sin energia no hay movimiento)."""
        for device in self._devices.values():
            device.shutdown()

    # ─── Callbacks de MQTT ───────────────────────────────────────────────

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code.is_failure:
            logger.error("[%s] El broker rechazo la conexion: %s", self.board_id, reason_code)
            return

        for device_key in self._devices:
            client.subscribe(contract.set_topic(device_key), qos=QOS)

        # Al conectarse, la placa se anuncia y cada dispositivo cuenta como esta
        client.publish(
            self._availability_topic, contract.AVAILABILITY_ONLINE, qos=QOS, retain=True
        )
        for device in self._devices.values():
            self._publish_state(device.device_key, device.current_state())

        logger.info("[%s] Placa conectada con %d dispositivo(s).", self.board_id, len(self._devices))

    def _on_message(self, client, userdata, message) -> None:
        # No se procesa aqui: se encola para respetar el orden y la latencia
        self._commands.put((message.topic, message.payload))

    # ─── Procesamiento de ordenes ────────────────────────────────────────

    def _process_commands(self) -> None:
        """Atiende las ordenes de una en una, como lo haria el hardware."""
        while True:
            item = self._commands.get()

            if item is None:
                return

            topic, payload = item
            device = self._find_device(topic)

            if device is None:
                logger.warning("[%s] Orden para un dispositivo que no maneja: %s", self.board_id, topic)
                continue

            time.sleep(self._settings.latency_seconds)

            try:
                new_state = device.handle_command(payload)
            except Exception:
                logger.exception("[%s] Error atendiendo una orden.", device.device_key)
                continue

            if new_state is None:
                logger.warning("[%s] Orden ignorada: %r", device.device_key, payload)
                continue

            logger.info("[%s] Orden aplicada -> %s", device.device_key, new_state)
            self._publish_state(device.device_key, new_state)

    def _find_device(self, topic: str) -> Optional[SimulatedDevice]:
        """Busca el dispositivo dueno del tema /set por el que llego la orden."""
        for device_key, device in self._devices.items():
            if topic == contract.set_topic(device_key):
                return device
        return None

    def _publish_state(self, device_key: str, state: str) -> None:
        elapsed_ms = int((time.monotonic() - self._started_at) * MS_PER_SECOND)
        self._client.publish(
            contract.state_topic(device_key),
            contract.encode_state(state, elapsed_ms),
            qos=QOS,
            retain=True,
        )
