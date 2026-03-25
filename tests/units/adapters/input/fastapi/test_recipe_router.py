import pytest
from fastapi.testclient import TestClient

from adapters.input.fastapi.recipe_router import RecipeRouter
from tests.units.adapters.input.fastapi.helpers import make_test_app


@pytest.fixture
def client(recipe_service, step_service, logger):
    app = make_test_app(RecipeRouter(recipe_service, step_service, logger).router)
    return TestClient(app)


def test_create_recipe(client):
    r = client.post("/v1/recipes/", json = {"name": "Pizza"})
    assert r.status_code == 201
    assert "uuid" in r.json()


def test_create_recipe_with_description(client):
    r = client.post("/v1/recipes/", json = {"name": "Pizza", "description": "Recette italienne", "nutriscore": "B"})
    assert r.status_code == 201


def test_list_recipes_empty(client):
    r = client.get("/v1/recipes/")
    assert r.status_code == 200
    assert r.json() == []


def test_list_recipes(client):
    client.post("/v1/recipes/", json = {"name": "Pizza"})
    client.post("/v1/recipes/", json = {"name": "Tarte Tatin"})
    r = client.get("/v1/recipes/")
    assert len(r.json()) == 2


def test_list_recipes_filter(client):
    client.post("/v1/recipes/", json = {"name": "Pizza Margherita"})
    client.post("/v1/recipes/", json = {"name": "Tarte Tatin"})
    r = client.get("/v1/recipes/?name=pizza")
    assert len(r.json()) == 1


def test_get_recipe(client):
    created = client.post("/v1/recipes/", json = {"name": "Pizza"}).json()
    r = client.get(f"/v1/recipes/{created['uuid']}")
    assert r.status_code == 200
    assert r.json()["name"] == "Pizza"


def test_get_recipe_not_found(client):
    from uuid6 import uuid7
    r = client.get(f"/v1/recipes/{uuid7()}")
    assert r.status_code == 404


def test_update_recipe(client):
    created = client.post("/v1/recipes/", json = {"name": "Pizza"}).json()
    r = client.put(f"/v1/recipes/{created['uuid']}", json = {"name": "Pizza Napolitaine"})
    assert r.status_code == 204


def test_update_recipe_unknown_uuid(client):
    from uuid6 import uuid7
    r = client.put(f"/v1/recipes/{uuid7()}", json = {"name": "Pizza"})
    assert r.status_code == 204


def test_patch_recipe(client):
    created = client.post("/v1/recipes/", json = {"name": "Pizza"}).json()
    r = client.patch(f"/v1/recipes/{created['uuid']}", json = {"description": "Délicieuse"})
    assert r.status_code == 204


def test_patch_recipe_not_found(client):
    from uuid6 import uuid7
    r = client.patch(f"/v1/recipes/{uuid7()}", json = {})
    assert r.status_code == 404


def test_delete_recipe(client):
    created = client.post("/v1/recipes/", json = {"name": "Pizza"}).json()
    r = client.delete(f"/v1/recipes/{created['uuid']}")
    assert r.status_code == 204


def test_duplicate_recipe(client):
    created = client.post("/v1/recipes/", json = {"name": "Pizza"}).json()
    r = client.post(f"/v1/recipes/{created['uuid']}/duplicate")
    assert r.status_code == 201
    assert r.json()["uuid"] != created["uuid"]


def test_list_recipes_with_steps(client):
    client.post("/v1/recipes/", json = {"name": "Pizza"})
    r = client.get("/v1/recipes/?include_steps=true")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_purge_recipes(client):
    r = client.delete("/v1/recipes/purge")
    assert r.status_code == 200
