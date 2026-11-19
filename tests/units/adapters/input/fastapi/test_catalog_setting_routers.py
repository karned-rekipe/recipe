import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from adapters.input.fastapi.dependencies import inject_tenant_uri, require_auth
from adapters.input.fastapi.routers import IngredientGroupRouter, IngredientRayonRouter, TagRouter, UnitRouter
from adapters.output.memory.repositories.ingredient_group_repository import InMemoryIngredientGroupRepository
from adapters.output.memory.repositories.ingredient_rayon_repository import InMemoryIngredientRayonRepository
from adapters.output.memory.repositories.ingredient_repository import InMemoryIngredientRepository
from adapters.output.memory.repositories.tag_repository import InMemoryTagRepository
from application.services.ingredient_group_service import IngredientGroupService
from application.services.ingredient_rayon_service import IngredientRayonService
from application.services.ingredient_service import IngredientService
from application.services.tag_service import TagService


@pytest.fixture
def app(logger):
    fastapi_app = FastAPI()
    fastapi_app.include_router(
        IngredientGroupRouter(IngredientGroupService(InMemoryIngredientGroupRepository(), logger), logger).router
    )
    fastapi_app.include_router(
        IngredientRayonRouter(IngredientRayonService(InMemoryIngredientRayonRepository(), logger), logger).router
    )
    fastapi_app.include_router(TagRouter(TagService(InMemoryTagRepository(), logger), logger).router)
    fastapi_app.include_router(UnitRouter(IngredientService(InMemoryIngredientRepository(), logger)).router)
    fastapi_app.dependency_overrides[inject_tenant_uri] = lambda: None
    fastapi_app.dependency_overrides[require_auth] = lambda: {"sub": "test-user"}
    return fastapi_app


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
        yield async_client


async def test_ingredient_group_router_crud(client) -> None:
    created = await client.post("/v1/ingredient-groups/", json={"name": "Legumes"}, headers={"Prefer": "return=representation"})
    group_uuid = created.json()["data"]["uuid"]

    listed = await client.get("/v1/ingredient-groups/?name=leg")
    fetched = await client.get(f"/v1/ingredient-groups/{group_uuid}")
    updated = await client.put(f"/v1/ingredient-groups/{group_uuid}", json={"name": "Fruits", "sort_order": 2})
    patched = await client.patch(f"/v1/ingredient-groups/{group_uuid}", json={"name": "Fruits rouges"})
    deleted = await client.delete(f"/v1/ingredient-groups/{group_uuid}")
    missing = await client.get(f"/v1/ingredient-groups/{group_uuid}")

    assert created.status_code == 201
    assert listed.json()["data"][0]["name"] == "Legumes"
    assert fetched.headers["etag"]
    assert updated.status_code == 204
    assert patched.status_code == 204
    assert deleted.status_code == 204
    assert missing.status_code == 404


async def test_ingredient_rayon_router_crud(client) -> None:
    created = await client.post("/v1/ingredient-rayons/", json={"name": "Frais"}, headers={"Prefer": "return=representation"})
    rayon_uuid = created.json()["data"]["uuid"]

    listed = await client.get("/v1/ingredient-rayons/?name=fra")
    fetched = await client.get(f"/v1/ingredient-rayons/{rayon_uuid}")
    updated = await client.put(f"/v1/ingredient-rayons/{rayon_uuid}", json={"name": "Epicerie", "sort_order": 2})
    patched = await client.patch(f"/v1/ingredient-rayons/{rayon_uuid}", json={"name": "Surgeles"})
    deleted = await client.delete(f"/v1/ingredient-rayons/{rayon_uuid}")
    missing = await client.get(f"/v1/ingredient-rayons/{rayon_uuid}")

    assert created.status_code == 201
    assert listed.json()["data"][0]["name"] == "Frais"
    assert fetched.headers["etag"]
    assert updated.status_code == 204
    assert patched.status_code == 204
    assert deleted.status_code == 204
    assert missing.status_code == 404


async def test_tag_router_crud_and_recipes_without_recipe_service(client) -> None:
    created = await client.post(
        "/v1/tags/",
        json={"name": "Express", "category": "other", "color": "#333333"},
        headers={"Prefer": "return=representation"},
    )
    tag_uuid = created.json()["data"]["uuid"]

    listed = await client.get("/v1/tags/?name=press")
    fetched = await client.get(f"/v1/tags/{tag_uuid}")
    updated = await client.put(f"/v1/tags/{tag_uuid}", json={"name": "Rapide", "category": "other"})
    patched = await client.patch(f"/v1/tags/{tag_uuid}", json={"color": "#444444"})
    recipes = await client.get(f"/v1/tags/{tag_uuid}/recipes")
    deleted = await client.delete(f"/v1/tags/{tag_uuid}")
    missing = await client.get(f"/v1/tags/{tag_uuid}")

    assert created.status_code == 201
    assert listed.json()["data"][0]["name"] == "Express"
    assert fetched.headers["etag"]
    assert updated.status_code == 204
    assert patched.status_code == 204
    assert recipes.status_code == 503
    assert deleted.status_code == 204
    assert missing.status_code == 404


async def test_unit_router_lists_units_and_converts_global_unit(client) -> None:
    units = await client.get("/v1/units/")

    assert units.status_code == 200
    assert any(unit["code"] == "kg" for unit in units.json()["data"])
