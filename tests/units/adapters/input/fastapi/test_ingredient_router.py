import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from adapters.input.fastapi.dependencies import inject_tenant_uri, require_auth
from adapters.input.fastapi.routers import IngredientRouter
from adapters.output.memory.repositories.ingredient_repository import InMemoryIngredientRepository
from adapters.output.memory.repositories.recipe_repository import InMemoryRecipeRepository
from application.services.ingredient_service import IngredientService
from application.services.recipe_service import RecipeService
from domain.models.recipe import Recipe
from domain.models.recipe_ingredient import RecipeIngredient
from infrastructure.purge_registry import PurgeRegistry
from uuid6 import UUID


def _payload(**kwargs) -> dict:
    return {"name": "Tomate", **kwargs}


@pytest.fixture
def ingredient_repo():
    return InMemoryIngredientRepository()


@pytest.fixture
def service(ingredient_repo, logger):
    return IngredientService(ingredient_repo, logger)


@pytest.fixture
def recipe_service(ingredient_repo, logger):
    return RecipeService(InMemoryRecipeRepository(), logger, ingredient_repository=ingredient_repo)


@pytest.fixture
def app(service, recipe_service, logger):
    fastapi_app = FastAPI()
    registry = PurgeRegistry()
    registry.register("ingredients", service.purge)
    fastapi_app.include_router(IngredientRouter(service, logger, recipe_service).router)
    fastapi_app.dependency_overrides[inject_tenant_uri] = lambda: None
    fastapi_app.dependency_overrides[require_auth] = lambda: {"sub": "test-user"}
    return fastapi_app


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def created(client):
    response = await client.post("/v1/ingredients/", json=_payload())
    return response.json()["data"]


# --- POST / ---

async def test_create_returns_201(client):
    response = await client.post("/v1/ingredients/", json=_payload())
    assert response.status_code == 201


async def test_create_returns_uuid(client):
    response = await client.post("/v1/ingredients/", json=_payload())
    data = response.json()
    assert data["status"] == "success"
    assert "uuid" in data["data"]


async def test_create_with_season_months(client):
    response = await client.post("/v1/ingredients/", json=_payload(season_months={"7": 3, "8": 3}))
    assert response.status_code == 201


async def test_create_invalid_season_month_raises_422(client):
    response = await client.post("/v1/ingredients/", json=_payload(season_months={"13": 2}))
    assert response.status_code == 422


# --- GET /{uuid} ---

async def test_get_found(client, created):
    uuid = created["uuid"]
    response = await client.get(f"/v1/ingredients/{uuid}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["name"] == "Tomate"


async def test_get_not_found(client):
    response = await client.get("/v1/ingredients/01951234-5678-7abc-def0-000000000000")
    assert response.status_code == 404


# --- PUT /{uuid} ---

async def test_update_returns_204(client, created):
    uuid = created["uuid"]
    response = await client.put(f"/v1/ingredients/{uuid}", json=_payload(name="Tomate cerise"))
    assert response.status_code == 204


async def test_update_not_found(client):
    response = await client.put(
        "/v1/ingredients/01951234-5678-7abc-def0-000000000000",
        json=_payload(name="Tomate cerise"),
    )
    assert response.status_code == 404


# --- PATCH /{uuid} ---

async def test_patch_returns_204(client, created):
    uuid = created["uuid"]
    response = await client.patch(f"/v1/ingredients/{uuid}", json={"name": "Tomate cerise"})
    assert response.status_code == 204


async def test_patch_not_found(client):
    response = await client.patch(
        "/v1/ingredients/01951234-5678-7abc-def0-000000000000",
        json={"name": "Tomate cerise"},
    )
    assert response.status_code == 404


# --- DELETE /{uuid} ---

async def test_delete_returns_204(client, created):
    uuid = created["uuid"]
    response = await client.delete(f"/v1/ingredients/{uuid}")
    assert response.status_code == 204


async def test_delete_then_get_returns_404(client, created):
    uuid = created["uuid"]
    await client.delete(f"/v1/ingredients/{uuid}")
    response = await client.get(f"/v1/ingredients/{uuid}")
    assert response.status_code == 404


# --- GET / (list) ---

async def test_list_returns_200(client):
    response = await client.get("/v1/ingredients/")
    assert response.status_code == 200


async def test_list_contains_created(client, created):
    response = await client.get("/v1/ingredients/")
    data = response.json()
    assert data["status"] == "success"
    names = [item["name"] for item in data["data"]]
    assert "Tomate" in names


async def test_list_filter_by_name(client):
    await client.post("/v1/ingredients/", json=_payload(name="Tomate cerise"))
    await client.post("/v1/ingredients/", json=_payload(name="Carotte"))
    response = await client.get("/v1/ingredients/?name=tomate")
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["name"] == "Tomate cerise"


async def test_list_duplicates_by_normalized_name(client):
    await client.post("/v1/ingredients/", json=_payload(name="Crème fraîche"))
    await client.post("/v1/ingredients/", json=_payload(name="Creme fraiche"))

    response = await client.get("/v1/ingredients/duplicates")

    assert response.status_code == 200
    groups = response.json()["data"]
    assert groups[0]["normalized_name"] == "creme fraiche"
    assert len(groups[0]["items"]) == 2


async def test_merge_duplicates_rewrites_recipes_and_soft_deletes_duplicate(client, recipe_service):
    target = (await client.post("/v1/ingredients/", json=_payload(name="Crème fraîche"))).json()["data"]["uuid"]
    duplicate = (await client.post("/v1/ingredients/", json=_payload(name="Creme fraiche"))).json()["data"]["uuid"]
    recipe = await recipe_service.create(Recipe(
        name="Sauce",
        servings=2,
        ingredients=[RecipeIngredient(ingredient_uuid=UUID(duplicate), quantity=1, unit="g")],
    ))

    response = await client.post(
        "/v1/ingredients/duplicates/merge",
        json={"target_uuid": target, "duplicate_uuids": [duplicate]},
    )

    assert response.status_code == 200
    assert response.json()["data"]["updated_recipe_count"] == 1
    assert (await client.get(f"/v1/ingredients/{duplicate}")).status_code == 404

    updated = await recipe_service.read(recipe.uuid)
    assert updated is not None
    assert str(updated.ingredients[0].ingredient_uuid) == target


# --- POST /{uuid}/duplicate ---

async def test_duplicate_returns_201(client, created):
    uuid = created["uuid"]
    response = await client.post(f"/v1/ingredients/{uuid}/duplicate")
    assert response.status_code == 201


async def test_duplicate_new_uuid(client, created):
    uuid = created["uuid"]
    response = await client.post(f"/v1/ingredients/{uuid}/duplicate")
    data = response.json()
    assert data["data"]["uuid"] != uuid
