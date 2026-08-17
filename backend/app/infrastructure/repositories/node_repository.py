"""
app/infrastructure/repositories/node_repository.py

Repositorio SQLite para la entidad Node y sus relaciones.

Responsabilidad: Implementar las operaciones de persistencia
de nodos, alias de voz y aristas del grafo usando SQLite.

Patron - Repository Pattern:
    - Encapsula toda la logica de acceso a datos para Node,
    NodeAlias y NodeEdge en un unico repositorio cohesivo,
    ya que estas tres entidades forman un agregado inseparable.

Principio SOLID aplicado:
    - D (Dependency Inversion): Implementa AbstractNodeRepository.
    - S (Single Responsibility): Solo gestiona persistencia del
    agregado Node (nodo + sus alias + sus aristas).
"""

import sqlite3
from typing import Optional
from app.domain.models import Node, NodeAlias, NodeEdge, UnityPosition, PhysicalPosition
from app.domain.interfaces import AbstractNodeRepository
from app.config import NODE_STATUS_ACTIVE

class SQLiteNodeRepository(AbstractNodeRepository):
    """
    Implementacion SQLite del repositorio de nodos.
    
    Gestiona la persistencia del agregado Node completo:
    el nodo mismo, sus alias de voz y sus aristas del grafo.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        """
        Inicializa el repositorio con una conexion activa.
        
        Args:
            connection: Conexion SQLite activa inyectada desde fuera.
        """
        self._connection = connection

    # -------------- Operaciones sobre Node --------------

    def create(self, node: Node) -> Node:
        """
        Crea un nuevo nodo en la base de datos y devuelve el nodo con su ID asignado.
        
        Args:
            node: Instancia de Node sin ID (id=None) a ser creada.

        Returns:
            RuntimeError: Si ocurre un error al insertar en la base de datos.
        """

        sql = """
            INSERT INTO nodes (
                house_id,
                node_type, 
                internal_name, 
                display_name, 
                unity_pos_x, 
                unity_pos_y, 
                unity_pos_z,
                physical_pos_x,
                physical_pos_y,
                status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        try:
            # Extraer coordenadas fisicas si existen
            phys_x = node.physical_position.x if node.physical_position else None
            phys_y = node.physical_position.y if node.physical_position else None

            cursor = self._connection.execute(sql, (
                node.house_id,
                node.node_type,
                node.internal_name,
                node.display_name,
                node.unity_position.x,
                node.unity_position.y,
                node.unity_position.z,
                phys_x,
                phys_y,
                node.status
            ))

            self._connection.commit()
            node.id = cursor.lastrowid
            return node
        
        except sqlite3.IntegrityError as error:
            self._connection.rollback()
            raise RuntimeError(f"Ya existe un nodo con ese nombre interno en esta casa: {error}")

        except sqlite3.Error as Error:
            self._connection.rollback()
            raise RuntimeError(f"Error al crear el nodo '{node.internal_name}': {Error}")
    
    def get_by_id(self, node_id: int) -> Optional[Node]:
        """
        Busca un nodo por su ID incluyendo todos sus alias.
        
        Args:
            node_id: ID unico del nodo.

        Returns:
            El nodo con su lista de alias o None si no existe.

        Raises:
            RuntimeError: Si ocurre un error al consultar la base de datos.
        """

        sql = "SELECT * FROM nodes WHERE id = ?"

        try:
            cursor = self._connection.execute(sql, (node_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            node = self._row_to_node(row)
            node.aliases = self._get_aliases_for_node(node_id)
            return node
        
        except sqlite3.Error as error:
            raise RuntimeError(f"Error al buscar el nodo por su ID {node_id}: {error}")
    
    def get_all_by_house(self, house_id: int) -> list[Node]:
        """
        Retorna todos los nodos activos de una casa con sus alias.
        
        Args: 
            house_id: ID de la casa que tiene esa lista de nodos.
        
        Returns:
            Lista de nodos activos de esa casa con sus alias cargados.

        Raises:
            RuntimeError: Si ocurre un error al consultar la base de datos.
        """

        sql = """
            SELECT * FROM nodes
            WHERE house_id = ? AND status = ?
            ORDER BY node_type ASC, display_name ASC
        """
        
        try:
            cursor = self._connection.execute(sql, (house_id,NODE_STATUS_ACTIVE))
            rows = cursor.fetchall()
            nodes = [self._row_to_node(row) for row in rows]

            # Carga los alias de cada nodo
            for node in nodes:
                node.aliases = self._get_aliases_for_node(node.id)
            
            return nodes
        
        except sqlite3.Error as error:
            raise RuntimeError(f"Error al obtener los nodos de la casa {house_id}: {error}")

    
    def update_display_name(self, node_id: int, display_name: str) -> Optional[Node]:
        """
        Actualiza el nombre visible (nombre editable por el usuario) de un nodo.
        
        Solo el display_name es modificable. El internal_name
        es inmutable porque el sistema de navegacion depende de el.

        Args:
            node_id: ID del nodo a actualizar.
            display_name: Nuevo nombre visible para el usuario.

        Returns:
            El nodo actualizado con sus alias o None si no existe.

        Raises:
            RuntimeError: Si ocurre un error al actualizar en la base de datos.
        """

        sql = """
            UPDATE nodes
            SET display_name = ?, updated_at = datetime('now')
            WHERE id = ?
        """

        try:
            cursor = self._connection.execute(sql, (display_name.strip(), node_id))
            self._connection.commit()

            if cursor.rowcount == 0:
                return None
            
            return self.get_by_id(node_id)
        
        except sqlite3.Error as error:
            raise RuntimeError(f"Error al actualizar el nombre del nodo {node_id}: {error}")

    
    def update_physical_position(self, node_id: int, x: float, y: float) -> Optional[Node]:
        """
        Actualiza la posicion fisica del nodo en la maqueta
        
        Args:
            node_id: ID del nodo a actualizar.
            x: Nueva coordenada X en la maqueta.
            y: Nueva coordenada Y en la maqueta.

        Returns:
            El nodo actualizado o None si no existe.

        Raises:
            RuntimeError: Si ocurre un error al actualizar en la base de datos.
        """
        sql = """
            UPDATE nodes
            SET physical_pos_x = ?, physical_pos_y = ?, updated_at = datetime('now')
            WHERE id = ?
        """

        try:
            cursor = self._connection.execute(sql, (x, y, node_id))
            self._connection.commit()

            if cursor.rowcount == 0:
                return None
            
            return self.get_by_id(node_id)
        
        except sqlite3.Error as error:
            raise RuntimeError(f"Error al actualizar posicion fisica del nodo {node_id}: {error}")
    
    def delete(self, node_id: int) -> bool:
        """
        Elimina un nodo y en cascada sus alias y aristas.
        
        El CASCADE definido en el schema garantiza que al
        eliminar el nodo se eliminan automaticamente sus
        alias y aristas relacionadas.

        Args:
            node_id: ID del nodo a eliminar.

        Returns:
            True si se elimino, False si no existia.

        Raises:
            RuntimeError: Si ocurre un error al intentar eliminar el nodo en la BD.
        """
        sql = "DELETE FROM nodes WHERE id = ?"
        
        try:
            cursor = self._connection.execute(sql, (node_id,))
            self._connection.commit()

            return cursor.rowcount > 0
        
        except sqlite3.Error as error:
            self._connection.rollback()
            raise RuntimeError(f"Error al eliminar el nodo {node_id}: {error}")
    
    # -------------- Operaciones sobre NodeAlias --------------

    def add_alias(self, alias: NodeAlias) -> NodeAlias:
        """
        Agrega un alias de voz a un nodo existente.
        
        Args:
            alias: Instancia de NodeAlias a persistir.

        Returns:
            El alias con su ID asignado por SQLite

        Raises:
            RuntimeError: Si el alias ya existe para ese nodo
                o si ocurre un error en la base de datos.
        """
        sql = """
            INSERT INTO node_aliases (node_id, alias)
            VALUES (?, ?)
        """

        try:
            cursor = self._connection.execute(sql, (alias.node_id, alias.alias))
            self._connection.commit()

            alias.id = cursor.lastrowid
            return alias
        
        except sqlite3.IntegrityError:
            self._connection.rollback()
            raise RuntimeError(
                f"El alias '{alias.alias}' ya existe para el nodo {alias.node_id}."
            )

        except sqlite3.Error as error:
            self._connection.rollback()
            raise RuntimeError(f"Error al agregar el alias '{alias.alias}': {error}")
    
    def delete_alias(self, alias_id: int) -> bool:
        """
        Elimina un alias de voz especifico por su ID.
        
        Args:
            alias_id: ID del alias a eliminar.

        Returns:
            True si se elimino, False si no existia.

        Raises:
            RuntimeError: Si ocurre un error al eliminar en la base de datos
        """
        
        sql = "DELETE FROM node_aliases WHERE id = ?"
        
        try:
            cursor = self._connection.execute(sql, (alias_id,))
            self._connection.commit()
            return cursor.rowcount > 0
        
        except sqlite3.Error as error:
            self._connection.rollback()
            raise RuntimeError(f"Error al eliminar el alias {alias_id}: {error}")
    
    # -------------- Operaciones sobre NodeEdge --------------

    def add_edge(self, edge: NodeEdge) -> NodeEdge:
        """
        Agrega una arista entre dos nodos del grafo.

        Args:
            edge: Instancia de NodeEdge a persistir.

        Returns:
            La arista con su ID asignado por SQLite.

        Raises:
            RuntimeError: Si la arista ya existe o hay un error en la base de datos.
        """

        sql = """
            INSERT INTO node_edges (
                from_node_id,
                to_node_id,
                weight,
                is_bidirectional
            ) VALUES (?, ?, ?, ?)
        """

        try:
            cursor = self._connection.execute(sql, (
                edge.from_node_id,
                edge.to_node_id,
                edge.weight,
                edge.is_bidirectional
            ))
            self._connection.commit()
            edge.id = cursor.lastrowid
            return edge
        
        except sqlite3.IntegrityError:
            self._connection.rollback()
            raise RuntimeError(
                f"Ya existe una arista entre los nodos "
                f"{edge.from_node_id} y {edge.to_node_id}."
            )
        
        except sqlite3.Error as error:
            self._connection.rollback()
            raise RuntimeError(f"Error al agregar la arista: {error}")
    
    def delete_edge(self, edge_id: int) -> bool:
        """
        Elimina una arista del grafo de navegacion
        
        Args:
            edge_id: ID de la arista a eliminar.

        Returns:
            True si se elimino, False si no existia

        RuntimeError:
            Si ocurre un error al eliminar de la base de datos
        """
        
        sql = "DELETE FROM node_edges WHERE id = ?"

        try:
            cursor = self._connection.execute(sql, (edge_id,))
            self._connection.commit()
            return cursor.rowcount > 0
        
        except sqlite3.Error as error:
            self._connection.rollback()
            raise RuntimeError(f"Error al eliminar la arista {edge_id}: {error}")

    
    # -------------- Metodos privados (traduccion BD → dominio) --------------

    def _row_to_node(self, row: sqlite3.Row) -> Node:
        """
        Traduce una fila de SQLite a un objeto Node del dominio.
        
        Reconstruye los Value Objects UnityPosition y
        PhysicalPosition desde las columnas individuales de la BD.

        Args:
            row: Fila de SQLite con los datos de un nodo.

        Returns:
            Instancia de Node construida desde la fila.
        """

        # Reconstruye PhysicalPosition solo si existen coordenadas fisicas
        physical_position = None

        if row["physical_pos_x"] is not None and row["physical_pos_y"] is not None:
            physical_position = PhysicalPosition(
                x=row["physical_pos_x"],
                y=row["physical_pos_y"]
            )

        return Node(
            id=row["id"],
            house_id=row["house_id"],
            node_type=row["node_type"],
            internal_name=row["internal_name"],
            display_name=row["display_name"],
            unity_position=UnityPosition(
                x=row["unity_pos_x"],
                y=row["unity_pos_y"],
                z=row["unity_pos_z"]
            ),
            physical_position=physical_position,
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
    
    def _get_aliases_for_node(self, node_id: int) -> list[NodeAlias]:
        """
        Consulta todos los alias de voz de un nodo especifico.
        
        Metodo auxiliar privado usado internamente para cargar
        los alias al reconstruir un Node completo.

        Args:
            node_id: ID del nodo propietario de los alias.

        Returns:
            Lista de los alias del nodo. Lista vacia si no tiene alias.
        """
        sql = "SELECT * FROM node_aliases WHERE node_id = ? ORDER BY alias ASC"

        cursor = self._connection.execute(sql, (node_id,))
        rows = cursor.fetchall()

        return [
            NodeAlias(
                id=row["id"],
                node_id=row["node_id"],
                alias=row["alias"],
                created_at=row["created_at"]
            )
            for row in rows
        ]