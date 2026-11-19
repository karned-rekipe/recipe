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


async def test_create_get_update_patch_list_recipes_and_delete(client, recipe_service):
    created_response = await client.post("/v1/equipment/", json=_payload(name="Four", description="Chaleur tournante"))

    assert created_response.status_code == 201
    assert created_response.headers["location"].startswith("/v1/equipment/")
    uuid = created_response.json()["data"]["uuid"]

    listed_response = await client.get("/v1/equipment/?name=four")
    assert listed_response.status_code == 200
    assert listed_response.headers["x-total-count"] == "1"
    assert listed_response.json()["data"][0]["name"] == "Four"

    fetched_response = await client.get(f"/v1/equipment/{uuid}")
    assert fetched_response.status_code == 200
    assert fetched_response.headers["etag"] == '"1"'
    assert 'rel="duplicate"' in fetched_response.headers["link"]

    update_response = await client.put(
        f"/v1/equipment/{uuid}",
        json=_payload(name="Four vapeur", description="Avec vapeur"),
        headers={"If-Match": '"1"'},
    )
    assert update_response.status_code == 204
    assert update_response.headers["content-location"] == f"/v1/equipment/{uuid}"

    patch_response = await client.patch(f"/v1/equipment/{uuid}", json={"description": "Compact"})
    assert patch_response.status_code == 204

    recipe = await recipe_service.create(Recipe(
        name="Gratin dauphinois",
        servings=4,
        equipment=[RecipeEquipment(equipment_uuid=UUID(uuid))],
    ))
    recipes_response = await client.get(f"/v1/equipment/{uuid}/recipes")
    assert recipes_response.status_code == 200
    assert recipes_response.headers["x-total-count"] == "1"
    assert recipes_response.json()["data"][0]["uuid"] == str(recipe.uuid)

    delete_used_response = await client.delete(f"/v1/equipment/{uuid}")
    assert delete_used_response.status_code == 409

    duplicate_response = await client.post(f"/v1/equipment/{uuid}/duplicate")
    assert duplicate_response.status_code == 201
    duplicate_uuid = duplicate_response.json()["data"]["uuid"]

    delete_duplicate_response = await client.delete(f"/v1/equipment/{duplicate_uuid}")
    assert delete_duplicate_response.status_code == 204
    assert (await client.get(f"/v1/equipment/{duplicate_uuid}")).status_code == 404


async def test_update_and_patch_reject_version_mismatch(client):
    uuid = (await client.post("/v1/equipment/", json=_payload(name="Robot"))).json()["data"]["uuid"]

    update_response = await client.put(
        f"/v1/equipment/{uuid}",
        json=_payload(name="Robot pâtissier"),
        headers={"If-Match": '"999"'},
    )
    patch_response = await client.patch(
        f"/v1/equipment/{uuid}",
        json={"description": "Bol inox"},
        headers={"If-Match": '"999"'},
    )

    assert update_response.status_code == 412
    assert patch_response.status_code == 412


async def test_missing_equipment_routes_return_404(client):
    missing_uuid = "01951234-5678-7abc-def0-000000000000"

    assert (await client.get(f"/v1/equipment/{missing_uuid}")).status_code == 404
    assert (await client.put(f"/v1/equipment/{missing_uuid}", json=_payload(name="Mandoline"))).status_code == 404
    assert (await client.patch(f"/v1/equipment/{missing_uuid}", json={"description": "Fine"})).status_code == 404
    assert (await client.get(f"/v1/equipment/{missing_uuid}/recipes")).status_code == 404


async def test_merge_duplicates_rejects_target_in_duplicate_list(client):
    uuid = (await client.post("/v1/equipment/", json=_payload(name="Mixeur"))).json()["data"]["uuid"]

    response = await client.post(
        "/v1/equipment/duplicates/merge",
        json={"target_uuid": uuid, "duplicate_uuids": [uuid]},
    )

    assert response.status_code == 409
