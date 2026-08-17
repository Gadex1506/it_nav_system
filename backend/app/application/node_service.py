"""
app/application/node_service.py

Servicio de logica de negocio para nodos, alias y aristas.

Responsabilidad: Orquestar las operaciones sobre el agregado de Node
aplicando todas las reglas de negocio del sistema como limite de alias,
validación de existencia de casa, integridad del grafo, etc.

Patrones aplicados:
    - Facade: Operaciones simples hacia endpoints ocultando
    la coordinacion interna.
    - Dependency Injection: Recibe repositorios desde afuera.

Principios SOLID aplicados:
    - S: Solo contiene logica de negocio del agregado Node.
    - D: Depende de abstracciones, no de implementaciones concretas.
"""

from typing import Optional
from app.domain.models import Node, NodeAlias, NodeEdge, UnityPosition, PhysicalPosition
from app.domain.interfaces import AbstractNodeRepository, AbstractHouseRepository
from app.config import (
    NODE_TYPE_ROOM,
    NODE_TYPE_WAYPOINT,
    MAX_ALIASES_PER_NODE,
)

class NodeService:
    """
    Servicio que gestiona la logica de negocio de nodos,
    alias de voz y aristas del grafo de navegacion.
    """

    def __init__(
            self,
            node_repository: AbstractNodeRepository,
            house_repository: AbstractHouseRepository,
        ) -> None:
        """
        Inicializa el servicio con sus repositorios inyectados.
        
        Recibe dos repositorios porque crear un nodo requiere
        verificar que la casa propietaria de ese nuevo nodo
        existe, lo cual es responsabilidad del repositorio de casas.

        Args:
            node_repository: Repositorio de nodos inyectado.
            house_repository: Repositorio de casas inyectado.
        """
        self._node_repo = node_repository
        self._house_repo = house_repository


    # -------------- Operaciones sobre Node --------------

    def create_node(
        self,
        house_id: int,
        node_type: str,
        internal_name: str,
        display_name: str,
        unity_x: float = 0.0,
        unity_y: float = 0.0,
        unity_z: float = 0.0,
        physical_x: Optional[float] = None,
        physical_y: Optional[float] = None,
    ) -> Node:
        """
        Crea un nuevo nodo validando todas las reglas de negocio.

        Verifica que la casa existe, construye los Value Objects
        de posicion y usa el Factory Method de Node para garantizar
        que el objeto nace de manera valida.

        Args:
            house_id: ID de la casa propietaria del nodo.
            node_type: Tipo del nodo ("room", o "waypoint")
            internal_name: Nombre tecnico unico e inmutable del nodo
            display_name: Nombre visible del nodo para el usuario
            unity_x: Coordenada X de la posicion del nodo en Unity.
            unity_y: Coordenada Y de la posicion del nodo en Unity.
            unity_z: Coordenada Z de la posicion del nodo en Unity.
            physical_x: Coordenada X de la posicion del nodo en la maqueta.
            physical_y: Coordenada Y de la posicion del nodo en la maqueta.

        Returns:
            El nodo creado con su ID asignado.

        Raises:
            ValueError: Si la casa no existe o los datos son invalidos.
            RuntimeError: Si ocurre un error de creacion del nodo.
        """

        # REGLA DE NEGOCIO: La casa debe existir antes de crear el nodo
        self._verify_house_exists(house_id)

        # Construye los Value Objects de posicion
        unity_position = UnityPosition(x=unity_x, y=unity_y, z=unity_z)

        physical_position = None

        if physical_x is not None and physical_y is not None:
            physical_position = PhysicalPosition(x=physical_x, y=physical_y)

        # Factory Method valida tipo, nombres y construye el Node
        node = Node.create(
            house_id=house_id,
            node_type=node_type,
            internal_name=internal_name,
            display_name=display_name,
            unity_position=unity_position,
            physical_position=physical_position,
        )

        return self._node_repo.create(node)
    
    def get_node(self, node_id: int) -> Optional[Node]:
        """
        Busca un nodo por su ID incluyendo sus alias
        
        Args:
            node_id: ID unico del nodo a consultar.

        Returns:
            El nodo con sus alias o None si no existe.
        """
        return self._node_repo.get_by_id(node_id)
    
    def get_nodes_by_house(self, house_id: int) -> list[Node]:
        """
        Retorna todos los nodos activos de una casa con sus alias.
        
        Args:
            house_id: ID unico de la casa.

        Returns:
            Lista de los nodos activos con sus alias cargados.
        """
        self._verify_house_exists(house_id)

        return self._node_repo.get_all_by_house(house_id)
    
    def rename_node(self, node_id: int, new_display_name: str) -> Node:
        """
        Actualiza el nombre visible de un nodo.
        
        Solo el display_name es editable. El internal_name
        es inmutable y nunca puede cambiarse desde este servicio.

        Args:
            node_id: ID unico del nodo a editar.
            new_display_name: Nuevo nombre visible para el nodo.

        Returns:
            EL nodo actualizado.

        Raises:
            ValueError: Si el nombre esta vacio o el nodo no existe.
        """

        if not new_display_name or not new_display_name.strip():
            raise ValueError("El nuevo nombre no puede estar vacio.")
        
        node = self._node_repo.update_display_name(node_id, new_display_name.strip())

        if not node:
            raise ValueError(f"No existe un nodo con ID {node_id}")
        
        return node
    
    def update_physical_position(
        self, node_id: int, x: float, y: float
    ) -> Node:
        """
        Actualiza la posicion fisica del nodo en la maqueta.

        Args:
            node_id: ID del nodo a actualizar.
            x: Nueva coordenada X en la maqueta.
            y: Nueva coordenada Y en la maqueta.

        Returns:
            El nodo actualizado.

        Raises:
            ValueError: Si el nodo no existe.
        """

        node = self._node_repo.update_physical_position(node_id, x, y)

        if not node:
            raise ValueError(f"No existe el nodo con ID {node_id}.")
        
        return node
    
    def delete_node(self, node_id: int) -> bool:
        """
        Elimina un nodo verificando que existe antes de borrarlo
        
        Args:
            node_id: ID unico del nodo a eliminar.

        Returns:
            True si se elimino correctamente.

        Raises:
            ValueError: Si el nodo no existe.
        """

        node = self._node_repo.get_by_id(node_id)

        if not node:
            raise ValueError(f"No existe el nodo con ID {node_id}.")
        
        return self._node_repo.delete(node_id)


    # -------------- Operaciones sobre NodeAlias --------------

    def add_alias_to_node(self, node_id: int, alias: str) -> NodeAlias:
        """
        Agrega un alias de voz a un nodo respetando el limite maximo de alias.
        
        REGLA DE NEGOCIO CENTRAL: Un nodo no puede tener mas de MAX_ALIASES_PER_NODE
        alias. Esta regla protege la simplicidad del sistema de reconocimiento de voz
        de ARIA.

        Args:
            node_id: ID del nodo al que se agrega el alias.
            alias: Texto del alias.

        Returns:
            El alias creado con su ID asignado.

        Raises:
            ValueError: Si el nodo no existe, el alias esta vacio,
                o se supero el limite de alias permitidos.
            RuntimeError: Si el alias ya existe para ese nodo.
        """

        # Verifica que el nodo existe y carga sus alias actuales
        node = self._node_repo.get_by_id(node_id)

        if not node:
            raise ValueError(f"No existe el nodo con el ID {node_id}")
        
        # REGLA DE NEGOCIO: limite maximo de alias por nodo
        current_alias_count = len(node.aliases)

        if current_alias_count >= MAX_ALIASES_PER_NODE:
            raise ValueError(
                f"El nodo '{node.display_name}' ya tiene el maximo de "
                f"{MAX_ALIASES_PER_NODE} alias permitidos. "
                "Elimina uno antes de agregar otro."
            )
        
        # Factory Method normaliza y valida el alias
        new_alias = NodeAlias.create(node_id=node_id, alias=alias)

        return self._node_repo.add_alias(new_alias)
    
    def delete_alias(self, alias_id: int) -> bool:
        """
        Elimina un alias de un nodo.
        
        Args:
            alias_id: ID unico del alias a eliminar

        Returns:
            True si se elimino correctamente.

        Raises:
            ValueError: Si el alias no existe.
        """

        alias_deleted = self._node_repo.delete_alias(alias_id)

        if not alias_deleted:
            raise ValueError(f"No existe el alias con ID {alias_id}.")
        
        return True


    # -------------- Operaciones sobre NodeEdge --------------

    def add_edge(
        self,
        from_node_id: int,
        to_node_id: int,
        weight: float = 1.0,
        is_bidirectional: bool = True,
    ) -> NodeEdge:
        """
        Agrega una arista entre dos nodos del grafo.
        
        Valida que ambos nodos existan antes de crear la conexion,
        garantizando la integridad del grafo de navegacion.

        Args:
            from_node_id: ID del nodo de origen.
            to_node_id: ID del nodo de destino.
            weight: Costo de la arista. Debe ser mayor a 0.
            is_bidirectional: True si la conexion es de ida y vuelta.

        Returns:
            La arista creada con su ID asignado.

        Raises:
            ValueError: Si alguno de los nodos no existe o
                los datos de la arista son incorrectos.
            RuntimeError: Si la arista ya existe entre esos nodos.
        """

        # REGLA DE NEGOCIO: Ambos nodos deben existir.
        self._verify_node_exists(from_node_id)
        self._verify_node_exists(to_node_id)

        # Factory Method valida que no sea un self_loop y peso > 0
        edge = NodeEdge.create(
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            weight=weight,
            is_bidirectional=is_bidirectional,
        )

        return self._node_repo.add_edge(edge)
    
    def delete_edge(self, edge_id: int) -> bool:
        """
        Elimina una arista del grafo de navegacion.
        
        Args:
            edge_id: ID unico de la arista a eliminar.

        Returns:
            True si se elimino correctamente.

        Raises:
            ValueError: Si la arista no existe.
        """

        edge_deleted = self._node_repo.delete_edge(edge_id)

        if not edge_deleted:
            raise ValueError(f"No existe la arista con ID {edge_id}")
        
        return True


    # -------------- Metodos privados (validaciones internas) --------------

    def _verify_house_exists(self, house_id: int) -> None:
        """
        Valida que una casa existe en el sistema.
        
        Metodo auxiliar privado que centraliza esta validacion
        para no repetirla en cada metodo publico que se necesite.

        Args:
            house_id: ID unico de la casa a validar.

        Returns:
            None.

        Raises:
            ValueError: Si la casa no existe.
        """

        house = self._house_repo.get_by_id(house_id)

        if not house:
            raise ValueError(
                f"No existe una casa con ID {house_id}. "
                "Registra la casa antes de operar sobre sus nodos."
            )
        
    def _verify_node_exists(self, node_id: int) -> None:
        """
        Valida que un nodo existe en el sistema.
        
        Metodo auxiliar privado que centraliza esta validacion
        para no repetirla en cada metodo que se necesite.

        Args:
            node_id: ID unico del nodo.

        Returns:
            None.

        Raises:
            ValueError: Si el nodo no existe.
        """

        node = self._node_repo.get_by_id(node_id)

        if not node:
            raise ValueError(
                f"No existe el nodo con ID {node_id}. "
            )