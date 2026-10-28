"""
simulator/backend_client.py

Consulta al backend para saber que luces estan registradas.

Asi el simulador crea automaticamente una luz falsa por cada luz que ya
registraste en el panel, sin que tengas que escribir los nombres a mano.
Usa solo la libreria estandar (urllib). GET /dev/devices no exige clave.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

from simulator.settings import HTTP_TIMEOUT_SECONDS

DEVICE_TYPE_LIGHT = "light"
DEVICE_TYPE_DOOR = "door"


class BackendUnavailableError(Exception):
    """No se pudo leer la lista de luces del backend."""


def fetch_registered_devices(backend_url: str, house_id: int, device_type: str) -> list[str]:
    """
    Pide al backend los device_key de los dispositivos de un tipo en una casa.

    Raises:
        BackendUnavailableError: Si el backend no responde o la respuesta es invalida.
    """
    query = urllib.parse.urlencode({"house_id": house_id, "device_type": device_type})
    url = f"{backend_url.rstrip('/')}/dev/devices?{query}"

    try:
        with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT_SECONDS) as response:
            devices = json.loads(response.read().decode("utf-8"))
        return [device["device_key"] for device in devices]

    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise BackendUnavailableError(
            f"No se pudo leer los dispositivos de {url}: {error}"
        ) from error
