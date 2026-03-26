import asyncio
import pytest
from fastapi.testclient import TestClient

from adapters.input.fastapi.routers.recipe_ustensil_router import RecipeUstensilRouter
from domain.models.recipe import Recipe
from domain.models.ustensil import Ustensil
from tests.units.adapters.input.fastapi.helpers import make_test_app


@pytest.fixture
def client(recipe_service, logger):
    app = make_test_app(RecipeUstensilRouter(recipe_service, logger).router)
    return TestClient(app)


@pytest.fixture
def recipe_uuid(recipe_service):
    recipe = asyncio.run(recipe_service.create(Recipe(name = "Pizza")))
    return str(recipe.uuid)


@pytest.fixture
def ustensil_uuid(ustensil_repo):
    ustensil = asyncio.run(ustensil_repo.create(Ustensil(name = "Fouet")))
    return str(ustensil.uuid)


def test_link_ustensil(client, recipe_uuid, ustensil_uuid):
    r = client.post(f"/v1/recipes/{recipe_uuid}/ustensils/{ustensil_uuid}")
    assert r.status_code == 201
    assert "uuid" in r.json()["data"]


def test_link_ustensil_recipe_not_found(client, ustensil_uuid):
    from uuid6 import uuid7
    r = client.post(f"/v1/recipes/{uuid7()}/ustensils/{ustensil_uuid}")
    assert r.status_code == 404


def test_link_ustensil_not_found(client, recipe_uuid):
    from uuid6 import uuid7
    r = client.post(f"/v1/recipes/{recipe_uuid}/ustensils/{uuid7()}")
    assert r.status_code == 404


def test_unlink_ustensil(client, recipe_uuid, ustensil_uuid):
    client.post(f"/v1/recipes/{recipe_uuid}/ustensils/{ustensil_uuid}")
    r = client.delete(f"/v1/recipes/{recipe_uuid}/ustensils/{ustensil_uuid}")
    assert r.status_code == 204


def test_list_recipe_ustensils(client, recipe_uuid, ustensil_uuid):
    client.post(f"/v1/recipes/{recipe_uuid}/ustensils/{ustensil_uuid}")
    r = client.get(f"/v1/recipes/{recipe_uuid}/ustensils/")
    assert r.status_code == 200
    assert len(r.json()["data"]) == 1


def test_list_recipe_ustensils_recipe_not_found(client):
    from uuid6 import uuid7
    r = client.get(f"/v1/recipes/{uuid7()}/ustensils/")
    assert r.status_code == 404


def test_unlink_ustensil_recipe_not_found(client, ustensil_uuid):
    from uuid6 import uuid7
    r = client.delete(f"/v1/recipes/{uuid7()}/ustensils/{ustensil_uuid}")
    assert r.status_code == 404
