"""
Tests de integracion para los endpoints de usuario final (/user).

Responsabilidad: Verificar que el usuario puede consultar y editar
nodos dentro de los limites permitidos, y que las reglas de negocio
(como el limite de alias) se respetan correctamente.
"""

def _create_sample_node(client):
    """
    Funcion auxiliar (no es un test): Crea un nodo de ejemplo
    reutilizable en varios tests para no repetir el mismo bloque.

    Args:
        client: TestClient inyectado por el fixture.

    Returns:
        Diccionario con los datos del nodo creado.
    """

    response = client.post("/dev/nodes", json={
        "house_id": 1,
        "node_type": "room",
        "internal_name": "master_bedroom",
        "display_name": "Habitacion Principal"
    })
    assert response.status_code == 201
    return response.json()

def test_get_nodes_returns_active_house_nodes(client):
    """
    El usuario debe poder listar los nodos de la casa activa.
    """
    _create_sample_node(client)

    response = client.get("/user/nodes")

    assert response.status_code == 200
    nodes = response.json()
    assert len(nodes) == 1
    assert nodes[0]["display_name"] == "Habitacion Principal"

def test_rename_node_updates_display_name(client):
    """
    El usuario debe poder renombrar un nodo, y el internal_name
    nunca debe cambiar en el proceso.
    """
    node = _create_sample_node(client)

    response = client.patch(
        f"/user/nodes/{node['id']}/display-name",
        json={"display_name": "Mi Cuarto"}
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["display_name"] == "Mi Cuarto"
    assert updated["internal_name"] == "MASTER_BEDROOM" # no cambia

def test_add_alias_to_node(client):
    """
    El usuario debe poder agregar un alias de voz a un nodo.
    """

    node = _create_sample_node(client)

    response = client.post(
        f"/user/nodes/{node['id']}/aliases",
        json={"alias": "Mi Cuarto Favorito"}
    )

    assert response.status_code == 201
    alias = response.json()
    assert alias["alias"] == "mi cuarto favorito" # Se normaliza a minusculas

def test_alias_limit_is_enforced(client):
    """
    El sistema no debe permitir mas de MAX_ALIASES_PER_NODE (5)
    alias para un mismo nodo. Este test valida la regla de negocio
    definida en NodeService.
    """

    node = _create_sample_node(client)

    # Agregamos 5 alias validos
    for i in range(5):
        response = client.post(
            f"/user/nodes/{node['id']}/aliases",
            json={"alias": f"alias {i}"}
        )
        assert response.status_code == 201

    # El sexto alias debe fallar
    sixth_alias = client.post(
            f"/user/nodes/{node['id']}/aliases",
            json={"alias": f"alias 6"}
        )
    assert sixth_alias.status_code == 400
    assert "maximo" in sixth_alias.json()["detail"]

def test_delete_alias_removes_it(client):
    """
    El usuario debe poder eliminar un alias especifico.
    """
    node = _create_sample_node(client)

    alias = client.post(
        f"/user/nodes/{node['id']}/aliases",
        json={"alias": "cuarto"}
    ).json()

    response = client.delete(
        f"/user/nodes/{node['id']}/aliases/{alias['id']}"
    )

    assert response.status_code == 200
    assert response.json()["success"] is True

def test_user_cannot_access_dev_endpoints_for_deletion(client):
    """
    Valida que router de usuario no expone la ruta de
    eliminacion de nodos que es exclusiva del desarrollador.
    """

    node = _create_sample_node(client)

    # Esta ruta no existe en /user, solo en /dev
    response = client.delete(f"/user/nodes/{node['id']}")

    # 405 =  metodo no permitido para esa ruta, o 404 si la ruta
    # no coincide con ningun patron definido en el user_router.
    assert response.status_code in (404, 405)