"""
simulator/__main__.py

Linea de comandos del simulador:  python -m simulator

Ejemplos:
    python -m simulator                         # una placa con una luz por cada luz registrada en el backend
    python -m simulator --lights light_sala --doors door_banio   # solo estos, sin consultar al backend
    python -m simulator --door-travel-ms 3000   # servo lento
    python -m simulator --latency-ms 1500       # hardware lento

Para detenerlo usa Ctrl+C. Eso SIMULA UN CORTE DE ENERGIA: el proceso
termina sin despedirse y el broker publica 'offline' por la placa (Last Will).
"""

import argparse
import logging
import sys
import time

from simulator import contract, settings
from simulator.backend_client import (
    DEVICE_TYPE_DOOR,
    DEVICE_TYPE_LIGHT,
    BackendUnavailableError,
    fetch_registered_devices,
)
from simulator.devices import SimulatedBoard, SimulatedDoor, SimulatedLight

IDLE_SLEEP_SECONDS = 1
EXIT_CODE_ERROR = 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m simulator", description="Simulador de la placa ESP32 de la casa (luces y puertas).")
    parser.add_argument("--lights", nargs="+", metavar="DEVICE_KEY",
                        help="Luces a simular.")
    parser.add_argument("--doors", nargs="+", metavar="DEVICE_KEY",
                        help="Puertas a simular. Si no indicas --lights ni --doors, se leen ambas del backend.")
    parser.add_argument("--board-id", default=contract.HOUSE_BOARD_ID,
                        help="Identificador de la placa simulada.")
    parser.add_argument("--backend-url", default=settings.DEFAULT_BACKEND_URL)
    parser.add_argument("--house-id", type=int, default=settings.DEFAULT_HOUSE_ID)
    parser.add_argument("--host", default=settings.DEFAULT_MQTT_HOST, help="Direccion del broker MQTT.")
    parser.add_argument("--port", type=int, default=settings.DEFAULT_MQTT_PORT)
    parser.add_argument("--user", default=settings.DEFAULT_MQTT_USER)
    parser.add_argument("--door-travel-ms", type=int, default=settings.DEFAULT_DOOR_TRAVEL_MS,
                        help="Milisegundos que tarda el servo en abrir o cerrar una puerta.")
    parser.add_argument("--door-hold-ms", type=int, default=settings.DEFAULT_DOOR_HOLD_MS,
                        help="Cierre de seguridad por defecto si la orden no trae hold_ms.")
    parser.add_argument("--latency-ms", type=int, default=settings.DEFAULT_LATENCY_MS,
                        help="Milisegundos que tarda cada dispositivo en reaccionar.")
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    args = build_parser().parse_args()

    if args.lights is None and args.doors is None:
        try:
            light_keys = fetch_registered_devices(args.backend_url, args.house_id, DEVICE_TYPE_LIGHT)
            door_keys = fetch_registered_devices(args.backend_url, args.house_id, DEVICE_TYPE_DOOR)
        except BackendUnavailableError as error:
            logging.error("%s", error)
            logging.error("Enciende el backend o indica los dispositivos con --lights / --doors.")
            return EXIT_CODE_ERROR
    else:
        light_keys = args.lights or []
        door_keys = args.doors or []

    if not light_keys and not door_keys:
        logging.error("No hay dispositivos para simular. Registralos en el panel o usa --lights / --doors.")
        return EXIT_CODE_ERROR

    sim_settings = settings.SimulatorSettings(
        host=args.host,
        port=args.port,
        username=args.user,
        password=settings.read_password(),
        latency_seconds=args.latency_ms / settings.MS_PER_SECOND,
    )

    logging.info("Placa '%s': %d luz(ces) y %d puerta(s).", args.board_id, len(light_keys), len(door_keys))
    logging.info("Broker: %s:%s como '%s'. Ctrl+C = corte de energia.", args.host, args.port, args.user)

    # Una sola placa con todos los dispositivos: una conexion, un Last Will
    devices = [SimulatedLight(key) for key in light_keys] + [
        SimulatedDoor(key, args.door_travel_ms / settings.MS_PER_SECOND,
                      args.door_hold_ms / settings.MS_PER_SECOND)
        for key in door_keys
    ]
    board = SimulatedBoard(args.board_id, devices, sim_settings)
    board.start()

    try:
        while True:
            time.sleep(IDLE_SLEEP_SECONDS)
    except KeyboardInterrupt:
        # Sin stop() a proposito: simula un corte de energia (dispara el Last Will)
        logging.info("Corte de energia simulado.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
