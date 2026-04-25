import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from uuid6 import UUID

from adapters.input.fastapi.dependencies import inject_tenant_uri, require_auth
from adapters.input.fastapi.routers import EquipmentRouter
from adapters.output.memory.repositories.equipment_repository import InMemoryEquipmentRepository
from adapters.output.memory.repositories.recipe_repository import InMemoryRecipeRepository
from application.services.equipment_service import EquipmentService
from application.services.recipe_service import RecipeService
from domain.models.recipe import Recipe
from domain.models.recipe_equipment import RecipeEquipment


def _payload(**kwargs) -> dict:
    return {"name": "Four", **kwargs}


@pytest.fixture
def equipment_repo():
    return InMemoryEquipmentRepository()


@pytest.fixture
def service(equipment_repo, logger):
    return EquipmentService(equipment_repo, logger)


@pytest.fixture
def recipe_service(equipment_repo, logger):
    return RecipeService(InMemoryRecipeRepository(), logger, equipment_repository=equipment_repo)


@pytest.fixture
def app(service, recipe_service, logger):
    fastapi_app = FastAPI()
    fastapi_app.include_router(EquipmentRouter(service, logger, recipe_service).router)
    fastapi_app.dependency_overrides[inject_tenant_uri] = lambda: None
    fastapi_app.dependency_overrides[require_auth] = lambda: {"sub": "test-user"}
    return fastapi_app


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_list_duplicates_by_normalized_name(client):
    await client.post("/v1/equipment/", json=_payload(name="Four vapeur"))
    await client.post("/v1/equipment/", json=_payload(name="four-vapeur"))

    response = await client.get("/v1/equipment/duplicates")

    assert response.status_code == 200
    groups = response.json()["data"]
    assert groups[0]["normalized_name"] == "four vapeur"
    assert len(groups[0]["items"]) == 2


async def test_merge_duplicates_rewrites_recipes_and_soft_deletes_duplicate(client, recipe_service):
    target = (await client.post("/v1/equipment/", json=_payload(name="Four vapeur"))).json()["data"]["uuid"]
    duplicate = (await client.post("/v1/equipment/", json=_payload(name="four-vapeur"))).json()["data"]["uuid"]
    recipe = await recipe_service.create(Recipe(
        name="Gratin",
        servings=4,
        equipment=[RecipeEquipment(equipment_uuid=UUID(duplicate))],
    ))

    response = await client.post(
        "/v1/equipment/duplicates/merge",
        json={"target_uuid": target, "duplicate_uuids": [duplicate]},
    )

    assert response.status_code == 200
    assert response.json()["data"]["updated_recipe_count"] == 1
    assert (await client.get(f"/v1/equipment/{duplicate}")).status_code == 404

    updated = await recipe_service.read(recipe.uuid)
    assert updated is not None
    assert str(updated.equipment[0].equipment_uuid) == target
