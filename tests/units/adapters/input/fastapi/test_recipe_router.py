import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from adapters.input.fastapi.dependencies import inject_tenant_uri, require_auth
from adapters.input.fastapi.routers import AdminRouter, RecipeRouter
from adapters.output.memory.repositories.equipment_repository import InMemoryEquipmentRepository
from adapters.output.memory.repositories.ingredient_repository import InMemoryIngredientRepository
from application.services.recipe_service import RecipeService
from domain.models.equipment import Equipment
from domain.models.ingredient import Ingredient
from infrastructure.purge_registry import PurgeRegistry
from uuid6 import UUID

INGREDIENT_UUID = "01951234-5678-7abc-def0-000000000101"
INGREDIENT_2_UUID = "01951234-5678-7abc-def0-000000000103"
EQUIPMENT_UUID = "01951234-5678-7abc-def0-000000000102"
EQUIPMENT_2_UUID = "01951234-5678-7abc-def0-000000000104"


def _complete_payload(**kwargs) -> dict:
    payload = {
        "name": "Farine",
        "description": "Recette de base",
        "servings": 4,
        "main_image": "https://example.com/recipe.jpg",
        "secondary_images": ["https://example.com/recipe-2.jpg"],
        "sources": [{"name": "Carnet", "description": "Version familiale", "uri": "https://example.com/farine"}],
        "ingredients": [{
            "ingredient_uuid": INGREDIENT_UUID,
            "quantity": 500,
            "unit": "g",
        }],
        "equipment": [{"equipment_uuid": EQUIPMENT_UUID, "quantity": 1}],
        "steps": [{
            "name": "Melanger",
            "description": "Melanger tous les ingredients.",
            "preparation_time": 10,
            "rest_time": 0,
            "cooking_time": 0,
            "rank": 1,
            "secondary_images": [],
        }],
    }
    payload.update(kwargs)
    return payload


@pytest.fixture
def ingredient_repo():
    repository = InMemoryIngredientRepository()
    ingredients = [
        Ingredient(uuid=UUID(INGREDIENT_UUID), name="Farine de ble", group="feculents", rayon="epicerie", green_score=80, unit="g"),
        Ingredient(uuid=UUID(INGREDIENT_2_UUID), name="Farine complete", group="feculents", rayon="epicerie", green_score=75, unit="g"),
    ]
    for ingredient in ingredients:
        repository._store[ingredient.uuid] = ingredient
    return repository


@pytest.fixture
def equipment_repo():
    repository = InMemoryEquipmentRepository()
    equipment_items = [
        Equipment(uuid=UUID(EQUIPMENT_UUID), name="Saladier"),
        Equipment(uuid=UUID(EQUIPMENT_2_UUID), name="Robot"),
    ]
    for equipment in equipment_items:
        repository._store[equipment.uuid] = equipment
    return repository


@pytest.fixture
def service(repo, ingredient_repo, equipment_repo, logger):
    return RecipeService(
        repo,
        logger,
        ingredient_repository=ingredient_repo,
        equipment_repository=equipment_repo,
    )


@pytest.fixture
def app(service, logger):
    fastapi_app = FastAPI()
    registry = PurgeRegistry()
    registry.register("recipes", service.purge)
    fastapi_app.include_router(RecipeRouter(service, logger).router)
    fastapi_app.include_router(AdminRouter(registry).router)
    fastapi_app.dependency_overrides[inject_tenant_uri] = lambda: None
    fastapi_app.dependency_overrides[require_auth] = lambda: {"sub": "test-user"}
    return fastapi_app


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def created(client):
    response = await client.post("/v1/recipes/", json=_complete_payload())
    return response.json()["data"]


async def test_create_returns_201(client):
    response = await client.post("/v1/recipes/", json=_complete_payload())
    assert response.status_code == 201


async def test_create_returns_uuid(client):
    response = await client.post("/v1/recipes/", json=_complete_payload())
    data = response.json()
    assert data["status"] == "success"
    assert "uuid" in data["data"]


async def test_create_rejects_incomplete_recipe(client):
    payload = _complete_payload()
    payload.pop("servings")
    response = await client.post("/v1/recipes/", json=payload)
    assert response.status_code == 422


async def test_create_minimal_recipe_returns_draft(client):
    response = await client.post("/v1/recipes/", json={"name": "Idee", "servings": 2})
    assert response.status_code == 201

    uuid = response.json()["data"]["uuid"]
    data = (await client.get(f"/v1/recipes/{uuid}")).json()["data"]

    assert data["status"] == "draft"
    assert data["ingredients"] == []
    assert data["equipment"] == []
    assert data["steps"] == []


async def test_create_recipe_with_ingredient_returns_active(client):
    response = await client.post("/v1/recipes/", json=_complete_payload())
    uuid = response.json()["data"]["uuid"]
    data = (await client.get(f"/v1/recipes/{uuid}")).json()["data"]
    assert data["status"] == "active"


async def test_create_recipe_with_component_projects_child_lines(client):
    child_response = await client.post(
        "/v1/recipes/",
        json=_complete_payload(name="Crème anglaise"),
    )
    child_uuid = child_response.json()["data"]["uuid"]

    parent_response = await client.post(
        "/v1/recipes/",
        json={
            "name": "Île flottante",
            "servings": 4,
            "components": [{
                "recipe_uuid": child_uuid,
                "label": "Crème anglaise",
                "rank": 1,
                "servings_multiplier": 2,
            }],
        },
    )
    parent_uuid = parent_response.json()["data"]["uuid"]
    data = (await client.get(f"/v1/recipes/{parent_uuid}")).json()["data"]

    assert data["status"] == "active"
    assert data["ingredients"][0]["quantity"] == 1000
    assert data["ingredients"][0]["line_origin"] == "component_projection"
    assert data["ingredients"][0]["source_recipe_uuid"] == child_uuid
    assert data["components"][0]["recipe_name"] == "Crème anglaise"
    assert data["components"][0]["ingredients"][0]["quantity"] == 1000


async def test_create_recipe_rejects_component_cycle(client):
    created = await client.post("/v1/recipes/", json={"name": "Caramel", "servings": 2})
    uuid = created.json()["data"]["uuid"]

    response = await client.patch(
        f"/v1/recipes/{uuid}",
        json={"components": [{"recipe_uuid": uuid, "label": "Caramel", "rank": 1}]},
    )

    assert response.status_code == 422


async def test_create_rejects_incomplete_ingredient_line(client):
    payload = _complete_payload(ingredients=[{"ingredient_uuid": INGREDIENT_UUID, "quantity": 500}])
    response = await client.post("/v1/recipes/", json=payload)
    assert response.status_code == 422


async def test_create_defaults_equipment_quantity(client):
    payload = _complete_payload(equipment=[{"equipment_uuid": EQUIPMENT_UUID}])
    response = await client.post("/v1/recipes/", json=payload)
    uuid = response.json()["data"]["uuid"]
    data = (await client.get(f"/v1/recipes/{uuid}")).json()["data"]
    assert data["equipment"][0]["quantity"] == 1


async def test_create_allows_no_steps(client):
    response = await client.post("/v1/recipes/", json=_complete_payload(steps=[]))
    assert response.status_code == 201
    uuid = response.json()["data"]["uuid"]
    data = (await client.get(f"/v1/recipes/{uuid}")).json()["data"]
    assert data["steps"] == []


async def test_create_rejects_partial_step_without_title(client):
    payload = _complete_payload(steps=[{"description": "Melanger.", "rank": 1}])
    response = await client.post("/v1/recipes/", json=payload)
    assert response.status_code == 422


async def test_get_found(client, created):
    uuid = created["uuid"]
    response = await client.get(f"/v1/recipes/{uuid}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["name"] == "Farine"
    assert data["data"]["servings"] == 4
    assert data["data"]["ingredients"][0]["name"] == "Farine de ble"
    assert data["data"]["equipment"][0]["name"] == "Saladier"
    assert data["data"]["steps"][0]["name"] == "Melanger"


async def test_get_not_found(client):
    response = await client.get("/v1/recipes/01951234-5678-7abc-def0-000000000000")
    assert response.status_code == 404


async def test_update_returns_204(client, created):
    uuid = created["uuid"]
    response = await client.put(
        f"/v1/recipes/{uuid}",
        json=_complete_payload(
            name="Farine complete",
            ingredients=[{
                "ingredient_uuid": INGREDIENT_2_UUID,
                "quantity": 500,
                "unit": "g",
            }],
        ),
    )
    assert response.status_code == 204


async def test_update_replaces_full_aggregate_and_preserves_creation_metadata(client, created):
    uuid = created["uuid"]
    before = (await client.get(f"/v1/recipes/{uuid}")).json()["data"]

    await client.put(
        f"/v1/recipes/{uuid}",
        json=_complete_payload(
            name="Farine complete",
            equipment=[{"equipment_uuid": EQUIPMENT_2_UUID, "quantity": 1}],
            steps=[{
                "name": "Petrir",
                "description": "Petrir la pate.",
                "preparation_time": 20,
                "rest_time": 60,
                "cooking_time": 0,
                "rank": 1,
                "secondary_images": [],
            }],
        ),
    )
    after = (await client.get(f"/v1/recipes/{uuid}")).json()["data"]

    assert after["name"] == "Farine complete"
    assert after["equipment"][0]["name"] == "Robot"
    assert after["steps"][0]["name"] == "Petrir"
    assert after["created_at"] == before["created_at"]
    assert after["version"] == before["version"] + 1


async def test_update_preserves_migration_metadata_when_omitted(client):
    created = (
        await client.post(
            "/v1/recipes/",
            json=_complete_payload(
                legacy_id=42,
                favorite=True,
                status="archived",
                quality_status="text_only",
                migration_metadata={"source_table": "mkg_recipe"},
            ),
        )
    ).json()["data"]
    uuid = created["uuid"]

    await client.put(f"/v1/recipes/{uuid}", json=_complete_payload(name="Farine T80"))
    after = (await client.get(f"/v1/recipes/{uuid}")).json()["data"]

    assert after["name"] == "Farine T80"
    assert after["legacy_id"] == 42
    assert after["favorite"] is True
    assert after["status"] == "active"
    assert after["quality_status"] == "text_only"
    assert after["migration_metadata"] == {"source_table": "mkg_recipe"}


async def test_patch_found_returns_204(client, created):
    uuid = created["uuid"]
    response = await client.patch(f"/v1/recipes/{uuid}", json={"name": "Farine T80"})
    assert response.status_code == 204


async def test_patch_preserves_unset_sections(client, created):
    uuid = created["uuid"]
    await client.patch(
        f"/v1/recipes/{uuid}",
        json={"ingredients": [{
            "ingredient_uuid": INGREDIENT_2_UUID,
            "quantity": 450,
            "unit": "g",
        }]},
    )
    response = await client.get(f"/v1/recipes/{uuid}")
    data = response.json()["data"]
    assert data["name"] == "Farine"
    assert data["ingredients"][0]["name"] == "Farine complete"
    assert data["equipment"][0]["name"] == "Saladier"
    assert data["steps"][0]["name"] == "Melanger"


async def test_patch_can_update_migration_quality_metadata(client, created):
    uuid = created["uuid"]
    await client.patch(
        f"/v1/recipes/{uuid}",
        json={
            "quality_status": "validated",
            "migration_metadata": {"source_table": "mkg_recipe", "qc_passed": True},
        },
    )

    response = await client.get(f"/v1/recipes/{uuid}")
    data = response.json()["data"]

    assert data["quality_status"] == "validated"
    assert data["migration_metadata"] == {"source_table": "mkg_recipe", "qc_passed": True}


async def test_patch_not_found_returns_404(client):
    response = await client.patch(
        "/v1/recipes/01951234-5678-7abc-def0-000000000000",
        json={"name": "X"},
    )
    assert response.status_code == 404


async def test_delete_returns_204(client, created):
    uuid = created["uuid"]
    response = await client.delete(f"/v1/recipes/{uuid}")
    assert response.status_code == 204


async def test_delete_recipe_used_as_component_returns_409(client):
    child = await client.post("/v1/recipes/", json=_complete_payload(name="Meringue"))
    child_uuid = child.json()["data"]["uuid"]
    await client.post(
        "/v1/recipes/",
        json={
            "name": "Île flottante",
            "servings": 4,
            "components": [{"recipe_uuid": child_uuid, "label": "Meringue", "rank": 1}],
        },
    )

    response = await client.delete(f"/v1/recipes/{child_uuid}")

    assert response.status_code == 409


async def test_delete_hides_from_get(client, created):
    uuid = created["uuid"]
    await client.delete(f"/v1/recipes/{uuid}")
    response = await client.get(f"/v1/recipes/{uuid}")
    assert response.status_code == 404


async def test_list_empty(client):
    response = await client.get("/v1/recipes/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["data"] == []
    assert data["pagination"]["total"] == 0


async def test_list_returns_all(client):
    await client.post("/v1/recipes/", json=_complete_payload(name="Farine"))
    await client.post("/v1/recipes/", json=_complete_payload(name="Sel"))
    response = await client.get("/v1/recipes/")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 2
    assert data["pagination"]["total"] == 2
    assert response.headers.get("x-total-count") == "2"


async def test_list_filtered_by_name(client):
    await client.post("/v1/recipes/", json=_complete_payload(name="Farine de ble"))
    await client.post("/v1/recipes/", json=_complete_payload(name="Sel fin"))
    response = await client.get("/v1/recipes/", params={"name": "farine"})
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["name"] == "Farine de ble"
    assert data["pagination"]["total"] == 1


async def test_list_filter_no_match(client):
    await client.post("/v1/recipes/", json=_complete_payload(name="Sel"))
    response = await client.get("/v1/recipes/", params={"name": "sucre"})
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []
    assert data["pagination"]["total"] == 0


async def test_list_meal_planner_eligible_excludes_drafts(client):
    await client.post("/v1/recipes/", json={"name": "Brouillon", "servings": 1})
    await client.post("/v1/recipes/", json=_complete_payload(name="Active"))

    response = await client.get("/v1/recipes/", params={"meal_planner_eligible": True})
    assert response.status_code == 200

    data = response.json()
    assert data["pagination"]["total"] == 1
    assert data["data"][0]["name"] == "Active"


async def test_duplicate_returns_201(client, created):
    uuid = created["uuid"]
    response = await client.post(f"/v1/recipes/{uuid}/duplicate")
    assert response.status_code == 201


async def test_duplicate_has_different_uuid_and_same_aggregate(client, created):
    uuid = created["uuid"]
    response = await client.post(f"/v1/recipes/{uuid}/duplicate", headers={"Prefer": "return=representation"})
    data = response.json()["data"]
    assert data["uuid"] != uuid
    assert data["ingredients"][0]["name"] == "Farine de ble"
    assert data["steps"][0]["name"] == "Melanger"


async def test_purge_returns_200(client):
    response = await client.delete("/admin/purge")
    assert response.status_code == 200


async def test_purge_returns_count(client):
    response = await client.delete("/admin/purge")
    data = response.json()
    assert "purged" in data
    assert "total" in data


async def test_purge_count_is_zero_when_nothing_eligible(client):
    await client.post("/v1/recipes/", json=_complete_payload())
    response = await client.delete("/admin/purge")
    assert response.json()["total"] == 0
