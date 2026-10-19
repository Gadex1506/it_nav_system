"""
Excepciones propias del dominio del sistema de navegacion.

Responsabilidad: Nombrar los errores de negocio que NO son simples
"valor invalido" (ValueError), para que la capa de presentacion
pueda traducirlos al codigo HTTP correcto sin leer el texto del mensaje.
"""


class HouseDeletionNotConfirmedError(Exception):
    """
    Se intento eliminar una casa sin confirmar correctamente su nombre.

    Eliminar una casa borra todos sus nodos, alias y aristas de forma
    definitiva, por eso se exige escribir el nombre exacto como
    proteccion contra eliminaciones accidentales.
    """

class DeviceKeyAlreadyExistsError(Exception):
    """
    Ya existe un dispositivo con ese device_key.

    El device_key es el identificador fijo que usa el contrato MQTT para el casod de las luces y puertas
    (por ejemplo 'light_living'), por eso no puede repetirse.
    """