import pytest
from fastapi.testclient import TestClient

from adapters.input.fastapi.routers.ingredient_router import IngredientRouter
from tests.units.adapters.input.fastapi.helpers import make_test_app


@pytest.fixture
def client(ingredient_service, logger):
    app = make_test_app(IngredientRouter(ingredient_service, logger).router)
    return TestClient(app)


def test_create_ingredient(client):
    r = client.post("/v1/ingredients/", json = {"name": "Farine", "unit": "g"})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "success"
    assert "uuid" in body["data"]


def test_create_ingredient_minimal(client):
    r = client.post("/v1/ingredients/", json = {"name": "Sel"})
    assert r.status_code == 201
    assert r.json()["status"] == "success"


def test_list_ingredients_empty(client):
    r = client.get("/v1/ingredients/")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "success"
    assert body["data"] == []


def test_list_ingredients(client):
    client.post("/v1/ingredients/", json = {"name": "Farine"})
    client.post("/v1/ingredients/", json = {"name": "Sel"})
    r = client.get("/v1/ingredients/")
    assert r.status_code == 200
    assert len(r.json()["data"]) == 2


def test_list_ingredients_filter(client):
    client.post("/v1/ingredients/", json = {"name": "Farine de blé"})
    client.post("/v1/ingredients/", json = {"name": "Sel fin"})
    r = client.get("/v1/ingredients/?name=farine")
    assert r.status_code == 200
    assert len(r.json()["data"]) == 1


def test_get_ingredient(client):
    created = client.post("/v1/ingredients/", json = {"name": "Farine"}).json()["data"]
    r = client.get(f"/v1/ingredients/{created['uuid']}")
    assert r.status_code == 200
    assert r.json()["data"]["name"] == "Farine"


def test_get_ingredient_not_found(client):
    from uuid6 import uuid7
    r = client.get(f"/v1/ingredients/{uuid7()}")
    assert r.status_code == 404


def test_update_ingredient(client):
    created = client.post("/v1/ingredients/", json = {"name": "Farine"}).json()["data"]
    r = client.put(f"/v1/ingredients/{created['uuid']}", json = {"name": "Farine complète"})
    assert r.status_code == 204


def test_update_ingredient_unknown_uuid(client):
    from uuid6 import uuid7
    r = client.put(f"/v1/ingredients/{uuid7()}", json = {"name": "Farine"})
    assert r.status_code == 204


def test_patch_ingredient(client):
    created = client.post("/v1/ingredients/", json = {"name": "Farine"}).json()["data"]
    r = client.patch(f"/v1/ingredients/{created['uuid']}", json = {"name": "Farine complète"})
    assert r.status_code == 204


def test_patch_ingredient_not_found(client):
    from uuid6 import uuid7
    r = client.patch(f"/v1/ingredients/{uuid7()}", json = {})
    assert r.status_code == 404


def test_delete_ingredient(client):
    created = client.post("/v1/ingredients/", json = {"name": "Farine"}).json()["data"]
    r = client.delete(f"/v1/ingredients/{created['uuid']}")
    assert r.status_code == 204


def test_duplicate_ingredient(client):
    created = client.post("/v1/ingredients/", json = {"name": "Farine"}).json()["data"]
    r = client.post(f"/v1/ingredients/{created['uuid']}/duplicate")
    assert r.status_code == 201
    assert r.json()["data"]["uuid"] != created["uuid"]


def test_purge_ingredients(client):
    r = client.delete("/v1/ingredients/purge")
    assert r.status_code == 200
