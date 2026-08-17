"""
app/application/house_service.py

Servicio de logica de negocio para la entidad House.

Responsabilidad: Orquestar las operaciones sobre casas aplicando
las reglas de negocio del sistema. No conoce SQLite ni HTTP,
solo coordina el dominio y los repositorios.

Patrones aplicados:
    - Facade: Expone operaciones simples ocultando la coordinacion
    interna entre dominio y repositorio.
    - Dependency Injection: Recibe el repositorio desde afuera,
    nunca lo instancia internamente.

Principios SOLID aplicados:
    - S: Solo contiene logica de negocio de House.
    - D: Depende de AbstractHouseRepository, no de SQLite.
"""

from typing import Optional
from app.domain.models import House
from app.domain.interfaces import AbstractHouseRepository

class HouseService:
    """
    Servicio que gestiona la logica de negocio de las casas.
    
    Actua como intermediario entre los endpoints HTTP y el
    repositorio de datos, aplicando validaciones y reglas
    de negocio antes de persistir o retornar informacion.
    """

    def __init__(self, repository: AbstractHouseRepository) -> None:
        """
        Inicializa el servicio con su repositorio inyectado.
        
        Args:
            repository: Implementacion del respositorio de casas.
                Se inyecta desde afuera (Dependency Injection).
        """
        
        # Depende de la abstraccion, no de SQLiteHouseRepository
        self._repository = repository

    def create_house(self, name: str, description: Optional[str] = None) -> House:
        """
        Crea una nueva casa validando sus datos de negocio.
        
        Usa el Factory Method de House para garantizar que
        el objeto nace en un estado valido antes de persistir.

        Args:
            name: Nombre de la casa. No puede estar vacio.
            description: Descripcion opcional de la instalacion.

        Returns:
            La casa creada con su ID asignado.

        Raises:
            ValueError: Si el nombre esta vacio.
            RuntimeError: Si ocurre un error de persistencia
        """

        # El Factory Method valida y construye el objeto
        house = House.create(name=name, description=description)
        return self._repository.create(house)
    
    def get_house(self, house_id: int) -> Optional[House]:
        """
        Busca una casa por su ID.
        
        Args:
            house_id: ID unico de la casa.

        Returns:
            La casa encontrada o None si no existe.
        """
        return self._repository.get_by_id(house_id)
    
    def get_all_houses(self) -> list[House]:
        """
        Retorna todas las casas registradas en el sistema.
        
        Returns:
            Lista de casas. Lista vacia si no hay ninguna
            casa registrada.
        """
        return self._repository.get_all()
    
    def verify_house_exists(self, house_id: int) -> House:
        """
        Verifica que una casa existe y la retorna.
        
        Metodo auxiliar usado por NodeService para validar
        que la casa propietaria de un nodo existe antes de
        crear el nodo.

        Args:
            house_id: ID unico de la casa a verificar.

        Returns:
            La casa encontrada.

        Raises:
            ValueError: Si la casa no existe en el sistema
        """
        house = self._repository.get_by_id(house_id)

        if not house:
            raise ValueError(
                f"No existe una casa con el ID: {house_id}. "
                "Verifica que la casa este registrada antes de crear nodos."
            )
        
        return house