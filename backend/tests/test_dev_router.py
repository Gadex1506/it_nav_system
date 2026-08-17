"""
Tests de integracion para los endpoints de desarrollador (/dev).

Responsabilidad: Verificar que el flujo completo de creacion de
nodos y aristas funciona correctamente de punta a punta, incluyendo
las validaciones de negocio implementadas en la capa de servicios.

Patron de organizacion: AAA (Arrange - Act - Assert) en cada test.
"""

def test_create_node_success(client):
    """
    Un nodo valido debe crearse correctamente y retomar sus datos
    """

    # Arrange: los datos del nodo a crear
    payload = {
        "house_id": 1,
        "node_type": "room",
        "internal_name": "living_room_01",
        "display_name": "Sala Principal",
        "unity_x": 1.5,
        "unity_y": 0.0,
        "unity_z": 3.2,
    }

    # Act: creamos el nodo
    response = client.post("/dev/nodes", json=payload)

    # Assert: verificamos que salio bien y con los datos correctos
    assert response.status_code == 201
    data = response.json()
    assert data["internal_name"] == "LIVING_ROOM_01" # se normaliza a mayusculas
    assert data["display_name"] == "Sala Principal"
    assert data["unity_position"]["x"] == 1.5
    assert data["aliases"] == []

def test_create_node_with_invalid_type_fails(client):
    """
    Un nodo con un node_type invalido debe ser rechazado antes
    de llegar a la base de datos.
    """

    payload = {
        "house_id": 1,
        "node_type": "garage", # tipo invalido, no existe en VALID_NODE_TYPES
        "internal_name": "garage_01",
        "display_name": "Garaje",
    }

    response = client.post("/dev/nodes", json=payload)

    # Pydantic rechaza esto en la validacion del schema (422)
    # antes incluso de llegar al servicio
    assert response.status_code == 422

def test_create_node_with_nonexistent_house_fails(client):
    """
    Crear un nodo con un house_id que no existe debe fallar
    con un error de negocio claro (400), no un error tecnico
    """

    payload = {
        "house_id": 999, # casa que no existe
        "node_type": "room",
        "internal_name": "phantom_room",
        "display_name": "Habitacion Fantasma",
    }

    response = client.post("/dev/nodes", json=payload)

    assert response.status_code == 400
    assert "No existe una casa" in response.json()["detail"]

def test_create_edge_between_two_nodes(client):
    """
    Dos nodos existentes deben poder conectarse con una arista.
    """

    # Arrange: creamos dos nodos primero
    node_a = client.post("/dev/nodes", json={
        "house_id": 1, "node_type": "waypoint",
        "internal_name": "hall_01", "display_name": "Pasillo 1"
    }).json()
    
    node_b = client.post("/dev/nodes", json={
        "house_id": 1, "node_type": "room",
        "internal_name": "kitchen_01", "display_name": "Cocina"
    }).json()

    # Act: los conectamos
    response = client.post("/dev/edges", json={
        "from_node_id": node_a["id"],
        "to_node_id": node_b["id"],
        "weight": 1.0,
        "is_bidirectional": True
    })

    # Assert
    assert response.status_code == 201
    edge = response.json()
    assert edge["from_node_id"] == node_a["id"]
    assert edge["to_node_id"] == node_b["id"]

def test_create_duplicate_edge_fails(client):
    """
    No se debe poder crear la misma arista dos veces entre
    los mismos dos nodos (restriccion de UNIQUE en la base de datos)
    """

    node_a = client.post("/dev/nodes", json={
        "house_id": 1, "node_type": "waypoint",
        "internal_name": "hall_02", "display_name": "Pasillo 2"
    }).json()
    
    node_b = client.post("/dev/nodes", json={
        "house_id": 1, "node_type": "room",
        "internal_name": "bedroom_01", "display_name": "Habitacion Principal"
    }).json()

    # Primera arista: debe funcionar
    first = client.post("/dev/edges", json={
        "from_node_id": node_a["id"],
        "to_node_id": node_b["id"],
    })
    assert first.status_code == 201

    second = client.post("/dev/edges", json={
        "from_node_id": node_a["id"],
        "to_node_id": node_b["id"],
    })
    assert second.status_code == 400

def test_delete_node_removes_edges(client):
    """
    Eliminar un nodo debe hacer que ya no se pueda consultar
    """
    node = client.post("/dev/nodes", json={
        "house_id": 1, "node_type": "room",
        "internal_name": "temp_room", "display_name": "Temporal"
    }).json()

    delete_response = client.delete(f"/dev/nodes/{node['id']}")

    assert delete_response.status_code == 200
    assert delete_response.json()["success"] is True

    # Verificamos que ya no existe
    get_response = client.get(f"/user/nodes/{node['id']}")
    assert get_response.status_code == 404