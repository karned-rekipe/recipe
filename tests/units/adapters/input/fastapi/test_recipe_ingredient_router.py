import asyncio
import pytest
from fastapi.testclient import TestClient

from adapters.input.fastapi.routers.recipe_ingredient_router import RecipeIngredientRouter
from domain.models.ingredient import Ingredient
from domain.models.recipe import Recipe
from tests.units.adapters.input.fastapi.helpers import make_test_app


@pytest.fixture
def client(recipe_service, logger):
    app = make_test_app(RecipeIngredientRouter(recipe_service, logger).router)
    return TestClient(app)


@pytest.fixture
def recipe_uuid(recipe_service):
    recipe = asyncio.run(recipe_service.create(Recipe(name = "Pizza")))
    return str(recipe.uuid)


@pytest.fixture
def ingredient_uuid(ingredient_repo):
    ingredient = asyncio.run(ingredient_repo.create(Ingredient(name = "Farine")))
    return str(ingredient.uuid)


def test_link_ingredient(client, recipe_uuid, ingredient_uuid):
    r = client.post(f"/v1/recipes/{recipe_uuid}/ingredients/{ingredient_uuid}")
    assert r.status_code == 201
    assert "uuid" in r.json()["data"]


def test_link_ingredient_recipe_not_found(client, ingredient_uuid):
    from uuid6 import uuid7
    r = client.post(f"/v1/recipes/{uuid7()}/ingredients/{ingredient_uuid}")
    assert r.status_code == 404


def test_link_ingredient_not_found(client, recipe_uuid):
    from uuid6 import uuid7
    r = client.post(f"/v1/recipes/{recipe_uuid}/ingredients/{uuid7()}")
    assert r.status_code == 404


def test_unlink_ingredient(client, recipe_uuid, ingredient_uuid):
    client.post(f"/v1/recipes/{recipe_uuid}/ingredients/{ingredient_uuid}")
    r = client.delete(f"/v1/recipes/{recipe_uuid}/ingredients/{ingredient_uuid}")
    assert r.status_code == 204


def test_list_recipe_ingredients(client, recipe_uuid, ingredient_uuid):
    client.post(f"/v1/recipes/{recipe_uuid}/ingredients/{ingredient_uuid}")
    r = client.get(f"/v1/recipes/{recipe_uuid}/ingredients/")
    assert r.status_code == 200
    assert len(r.json()["data"]) == 1


def test_list_recipe_ingredients_recipe_not_found(client):
    from uuid6 import uuid7
    r = client.get(f"/v1/recipes/{uuid7()}/ingredients/")
    assert r.status_code == 404


def test_unlink_ingredient_recipe_not_found(client, ingredient_uuid):
    from uuid6 import uuid7
    r = client.delete(f"/v1/recipes/{uuid7()}/ingredients/{ingredient_uuid}")
    assert r.status_code == 404
