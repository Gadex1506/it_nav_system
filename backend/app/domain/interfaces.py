"""
# app/domain/interfaces.py

Contratos abstractos del dominio del sistema de navegacion.

Responsabilidad: Definir las interfaces que deben implementar
los repositorios de infraestructura. El dominio y la capa de
aplicacion dependen de estas abstracciones, nunca de las
implementaciones concretas de SQLite.

Principios SOLID aplicados:
    - D (Dependency Inversion): Las capas superiores dependen
    de estas abstracciones, no de SQLite directamente.
    - I (Interface Segregation): Una interfaz por repositorio,
    con solo los metodos que cada uno necesita.
    - O (Open/Closed): Nuevas implementaciones (ej: PostgreSQL)
    se agregan implementando estas interfaces sin modificarlas.
"""

from abc import ABC, abstractmethod
from typing import Optional
from app.domain.models import House, Node, NodeAlias, NodeEdge

class AbstractHouseRepository(ABC):
    """
    Contrato abstracto para el repositorio de casas.
    
    Define las operaciones que cualquier implementacion
    de repositorio de casas debe proveer para gestionar casas.
    """

    @abstractmethod
    def create(self, house: House) -> House:
        """
        Crea una nueva casa en el repositorio.

        Args:
            house: Instancia de House a persistir.

        Returns:
            La misma casa con su ID asignado por la BD.
        """
        ...

    @abstractmethod
    def get_by_id(self, house_id: int) -> Optional[House]:
        """
        Busca una casa por su ID.
        
        Args:
            house_id: ID unico de la casa a buscar.

        Returns:
            La casa encontrada o None si no existe.
        """
        ...

    @abstractmethod
    def get_all(self) -> list[House]:
        """
        Retorna todas las casas registradas.
        
        Returns:
            Lista de todas las casas en el repositorio. Lista vacia si no hay niguna.
        """
        ...

class AbstractNodeRepository(ABC):
    """
    Contrato abstracto para el repositorio de nodos.
    
    Define las operaciones que cualquier implementacion
    de repositorio de nodos debe proveer para gestionar nodos,
    sus alias y sus aristas.
    """

    @abstractmethod
    def create(self, node: Node) -> Node:
        """
        Crea un nuevo nodo en el repositorio.

        Args:
            node: Instancia de Node a persistir.

        Returns:
            El mismo nodo con su ID asignado por la BD.
        """
        ...

    @abstractmethod
    def get_by_id(self, node_id: int) -> Optional[Node]:
        """
        Busca un nodo por su ID incluyendo sus alias.
        
        Args:
            node_id: ID uncio del nodo.

        Returns:
            El nodo encontrado con sus alias o None si no existe.
        """
        ...

    @abstractmethod
    def get_all_by_house(self, house_id: int) -> list[Node]:
        """
        Retorna todos los nodos activos de una casa especifica.
        

        Args:
            house_id: ID de la casa a la que pertenecen los nodos.

        Returns:
            Lista de nodos activos en esa casa con sus alias. Lista vacia si no hay niguno.
        """
        ...

    @abstractmethod
    def update_display_name(self, node_id: int, display_name: str) -> Optional[Node]:
        """
        Actualiza el nombre visible de un nodo.
        
        Solo el display_name es editable por el usuario.
        El internal_name nunca cambia.

        Args:
            node_id: ID del nodo a actualizar.
            display_name: Nuevo nombre visible para el nodo.

        Returns:
            El nodo actualizado o None si no existe.
        """
        ...

    @abstractmethod
    def update_physical_position(
        self, node_id: int, x: float, y: float
    ) -> Optional[Node]:
        """
        Actualiza la posicion fisica del nodo en la maqueta.
        
        Args:
            node_id: ID del nodo a actualizar.
            x: Nueva coordenada X en la maqueta.
            y: Nueva coordenada Y en la maqueta.

        Returns:
            El nodo actualizado o None si no existe.
        """
        ...

    @abstractmethod
    def delete(self, node_id: int) -> bool:
        """
        Elimina un nodo y sus datos relacionados (alias, aristas) del repositorio.

        Gracias al CASCADE en el schema, eliminar el nodo
        elimina automaticamente sus alias y aristas.

        Args:
            node_id: Id del nodo a eliminar.

        Returns:
            True si se elimino correctamente, False si no existia.
        """
        ...

    @abstractmethod
    def add_alias(self, alias: NodeAlias) -> NodeAlias:
        """
        Agrega un alias de voz a un nodo existente.

        Args:
            alias: Instancia de NodeAlias a agregar. Debe tener un node_id valido.

        Returns:
            El alias con su ID asignado por la BD.
        """
        ...

    @abstractmethod
    def delete_alias(self, alias_id: int) -> bool:
        """
        Elimina un alias de voz especifico de un nodo.
        
        Args:
            alias_id: ID del alias a eliminar.

        Returns:
            True si se elimino correctamente, False si no existia.
        """
        ...

    @abstractmethod
    def add_edge(self, edge: NodeEdge) -> NodeEdge:
        """
        Agrega una arista entre dos nodos del grafo.
        
        Args:
            edge: Instancia de NodeEdge a agregar. 
                Debe tener from_node_id y to_node_id validos.

        Returns:
            La arista con su ID asignado por la BD.
        """
        ...

    @abstractmethod
    def delete_edge(self, edge_id: int) -> bool:
        """
        Elimina una arista especifica del grafo de navegacion.
        
        Args:
            edge_id: ID de la arista a eliminar.

        Returns:
            True si se elimino correctamente, False si no existia.
        """
        ...