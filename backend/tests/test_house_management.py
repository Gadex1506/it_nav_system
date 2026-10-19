"""
Pruebas de gestion de casas (crear, listar, eliminar) y de la
proteccion por clave de desarrollador.
"""

NODE_PAYLOAD = {
    "house_id": 1, "node_type": "room", "internal_name": "SALA",
    "display_name": "Sala", "unity_x": 0, "unity_y": 0, "unity_z": 0,
}


def _create_house(client, name):
    response = client.post("/dev/houses", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def test_create_house_without_key_is_rejected(client):
    response = client.post("/dev/houses", json={"name": "X"}, headers={"X-Dev-Key": ""})
    assert response.status_code == 401


def test_wrong_key_is_rejected(client):
    response = client.get("/dev/houses/overview", headers={"X-Dev-Key": "incorrecta"})
    assert response.status_code == 401


def test_overview_marks_active_house_and_counts_nodes(client):
    assert client.post("/dev/nodes", json=NODE_PAYLOAD).status_code == 201
    data = client.get("/dev/houses/overview").json()
    assert data["active_house_id"] == 1
    assert data["houses"][0]["node_count"] == 1 and data["houses"][0]["is_active"] is True


def test_delete_requires_exact_name(client):
    house_id = _create_house(client, "Casa Borrable")
    response = client.delete(f"/dev/houses/{house_id}", params={"confirm_name": "otra"})
    assert response.status_code == 409
    assert len(client.get("/dev/houses").json()) == 2


def test_delete_unknown_house_returns_404(client):
    response = client.delete("/dev/houses/999", params={"confirm_name": "x"})
    assert response.status_code == 404


def test_delete_removes_nodes_aliases_and_edges(client):
    house_id = _create_house(client, "Casa Borrable")
    ids = []
    for name in ("A", "B"):
        payload = {**NODE_PAYLOAD, "house_id": house_id, "internal_name": name}
        ids.append(client.post("/dev/nodes", json=payload).json()["id"])
    assert client.post(f"/dev/nodes/{ids[0]}/aliases", json={"alias": "uno"}).status_code == 201
    assert client.post("/dev/edges", json={"from_node_id": ids[0], "to_node_id": ids[1]}).status_code == 201

    response = client.delete(f"/dev/houses/{house_id}", params={"confirm_name": "Casa Borrable"})
    assert response.status_code == 200

    from app.infrastructure.database import get_db
    db = get_db()
    for table in ("nodes", "node_aliases", "node_edges"):
        remaining = db.execute(
            f"SELECT COUNT(*) FROM {table}" + (" WHERE house_id = ?" if table == "nodes" else ""),
            (house_id,) if table == "nodes" else ()
        ).fetchone()[0]
        assert remaining == 0, table


def test_delete_keeps_other_houses_data(client):
    other = _create_house(client, "Otra")
    client.post("/dev/nodes", json={**NODE_PAYLOAD, "house_id": other, "internal_name": "Z"})
    client.delete(f"/dev/houses/{other}", params={"confirm_name": "Otra"})
    data = client.get("/dev/houses/overview").json()
    assert [h["name"] for h in data["houses"]] == ["Casa de Prueba"]


def test_active_house_is_lowest_id_and_survives_recreate(client):
    # Borrar la casa activa y crear otra. La nueva pasa a ser la activa sin tocar app.config
    client.delete("/dev/houses/1", params={"confirm_name": "Casa de Prueba"})
    assert client.get("/dev/houses/overview").json()["active_house_id"] is None
    new_id = _create_house(client, "Nueva")
    data = client.get("/dev/houses/overview").json()
    assert new_id != 1 and data["active_house_id"] == new_id
    assert data["houses"][0]["is_active"] is True


def test_service_get_active_house_without_houses_raises(client):
    import pytest
    from app.application.house_service import HouseService
    from app.infrastructure.database import get_db
    from app.infrastructure.repositories.house_repository import SQLiteHouseRepository
    client.delete("/dev/houses/1", params={"confirm_name": "Casa de Prueba"})
    with pytest.raises(ValueError):
        HouseService(SQLiteHouseRepository(get_db())).get_active_house()
