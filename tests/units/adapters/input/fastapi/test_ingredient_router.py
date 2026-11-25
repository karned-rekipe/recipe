import pytest
from unittest.mock import AsyncMock
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from adapters.input.fastapi.dependencies import inject_tenant_uri, require_auth
from adapters.input.fastapi.routers import IngredientRouter
from adapters.output.memory.repositories.ingredient_enrichment_suggestion_repository import (
    InMemoryIngredientEnrichmentSuggestionRepository,
)
from adapters.output.memory.repositories.ingredient_repository import InMemoryIngredientRepository
from adapters.output.memory.repositories.recipe_repository import InMemoryRecipeRepository
from application.services.ingredient_enrichment_suggestion_service import IngredientEnrichmentSuggestionService
from application.services.ingredient_service import IngredientService
from application.services.recipe_service import RecipeService
from domain.models.recipe import Recipe
from domain.models.ingredient_image_generation import IngredientImageGeneration
from domain.ports.output.ingredient_image_generation_agent import IngredientImageGenerationAgent
from domain.models.recipe_ingredient import RecipeIngredient
from infrastructure.purge_registry import PurgeRegistry
from uuid6 import UUID


def _payload(**kwargs) -> dict:
    return {"name": "Tomate", **kwargs}


@pytest.fixture
def ingredient_repo():
    return InMemoryIngredientRepository()


@pytest.fixture
def image_generation_agent():
    agent = AsyncMock(spec=IngredientImageGenerationAgent)

    async def generate(*, ingredient_uuid: str):
        return IngredientImageGeneration(
            run_uuid="01951234-5678-7abc-def0-000000000301",
            ingredient_uuid=ingredient_uuid,
            suggestion_uuid="01951234-5678-7abc-def0-000000000302",
            status="success",
            completeness_score=25,
            missing_fields=["media_profile"],
            proposed_fields=["media_profile"],
        )

    agent.generate.side_effect = generate
    return agent


@pytest.fixture
def service(ingredient_repo, logger, image_generation_agent):
    return IngredientService(
        ingredient_repo,
        logger,
        image_generation_agent=image_generation_agent,
    )


@pytest.fixture
def recipe_service(ingredient_repo, logger):
    return RecipeService(InMemoryRecipeRepository(), logger, ingredient_repository=ingredient_repo)


@pytest.fixture
def suggestion_service(ingredient_repo, logger):
    return IngredientEnrichmentSuggestionService(
        InMemoryIngredientEnrichmentSuggestionRepository(),
        ingredient_repo,
        logger,
    )


@pytest.fixture
def app(service, recipe_service, suggestion_service, logger):
    fastapi_app = FastAPI()
    registry = PurgeRegistry()
    registry.register("ingredients", service.purge)
    fastapi_app.include_router(IngredientRouter(service, logger, recipe_service, suggestion_service).router)
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


async def test_generate_ingredient_image_uses_recipe_facade(
    client,
    created,
    image_generation_agent,
):
    uuid = created["uuid"]

    response = await client.post(f"/v1/ingredients/{uuid}/main-image", json={})

    assert response.status_code == 201
    assert response.json()["data"]["ingredient_uuid"] == uuid
    assert response.json()["data"]["proposed_fields"] == ["media_profile"]
    image_generation_agent.generate.assert_awaited_once_with(ingredient_uuid=uuid)


async def test_generate_ingredient_image_rejects_free_form_parameters(client, created):
    response = await client.post(
        f"/v1/ingredients/{created['uuid']}/main-image",
        json={"brief": "Generate anything"},
    )

    assert response.status_code == 422


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


async def test_pending_image_suggestion_survives_detail_and_list_reload(client, created):
    ingredient_uuid = created["uuid"]
    image_uri = "/api/media/v1/buckets/ingredients/objects/tomate.png"
    suggestion_response = await client.post(
        f"/v1/ingredients/{ingredient_uuid}/enrichment-suggestions",
        json={
            "run_uuid": "01951234-5678-7abc-def0-000000000451",
            "proposed_patch": {
                "media_profile": {
                    "main_image_uri": image_uri,
                    "image_status": "generated",
                    "source": "ai",
                    "validated": False,
                },
            },
            "field_confidences": {"media_profile": 0.8},
            "field_sources": {"media_profile": "ai"},
        },
    )
    suggestion_uuid = suggestion_response.json()["data"]["uuid"]

    detail = (await client.get(f"/v1/ingredients/{ingredient_uuid}")).json()["data"]
    listed = (await client.get("/v1/ingredients/")).json()["data"][0]

    assert detail["media_profile"]["main_image_uri"] is None
    assert detail["suggested_media_profile"]["main_image_uri"] == image_uri
    assert detail["suggested_media_profile"]["validated"] is False
    assert listed["suggested_media_profile"]["main_image_uri"] == image_uri

    reject_response = await client.post(
        f"/v1/ingredients/{ingredient_uuid}/enrichment-suggestions/{suggestion_uuid}/reject",
        json={"fields": ["media_profile"]},
    )
    rejected_detail = (await client.get(f"/v1/ingredients/{ingredient_uuid}")).json()["data"]

    assert reject_response.status_code == 200
    assert rejected_detail["suggested_media_profile"] is None


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


async def test_update_and_patch_reject_version_mismatch(client, created):
    uuid = created["uuid"]

    update_response = await client.put(
        f"/v1/ingredients/{uuid}",
        json=_payload(name="Tomate ancienne"),
        headers={"If-Match": '"999"'},
    )
    patch_response = await client.patch(
        f"/v1/ingredients/{uuid}",
        json={"green_score": 80},
        headers={"If-Match": '"999"'},
    )

    assert update_response.status_code == 412
    assert patch_response.status_code == 412


async def test_list_recipes_for_ingredient_and_delete_conflict(client, created, recipe_service):
    uuid = created["uuid"]
    recipe = await recipe_service.create(Recipe(
        name="Sauce tomate",
        servings=2,
        ingredients=[RecipeIngredient(ingredient_uuid=UUID(uuid), quantity=200, unit="g")],
    ))

    recipes_response = await client.get(f"/v1/ingredients/{uuid}/recipes")
    delete_response = await client.delete(f"/v1/ingredients/{uuid}")

    assert recipes_response.status_code == 200
    assert recipes_response.headers["x-total-count"] == "1"
    assert recipes_response.json()["data"][0]["uuid"] == str(recipe.uuid)
    assert delete_response.status_code == 409


async def test_list_recipes_for_missing_ingredient_returns_404(client):
    response = await client.get("/v1/ingredients/01951234-5678-7abc-def0-000000000000/recipes")

    assert response.status_code == 404


async def test_convert_unit_uses_ingredient_specific_profile(client):
    created = (await client.post(
        "/v1/ingredients/",
        json=_payload(
            name="Oeuf",
            unit_profile={
                "reference_unit": "piece",
                "conversions": [
                    {"from_unit": "piece", "to_unit": "g", "factor": 55, "source": "ingredient_specific"},
                ],
            },
        ),
    )).json()["data"]

    response = await client.post(
        f"/v1/ingredients/{created['uuid']}/convert",
        json={"quantity": 2, "from_unit": "piece", "to_unit": "g"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["converted_quantity"] == 110
    assert response.json()["data"]["source"] == "ingredient_specific"


async def test_convert_unit_without_available_conversion_returns_422(client, created):
    response = await client.post(
        f"/v1/ingredients/{created['uuid']}/convert",
        json={"quantity": 2, "from_unit": "piece", "to_unit": "ml"},
    )

    assert response.status_code == 422


async def test_enrichment_suggestion_http_lifecycle(client, created):
    ingredient_uuid = created["uuid"]
    suggestion_response = await client.post(
        f"/v1/ingredients/{ingredient_uuid}/enrichment-suggestions",
        json={
            "run_uuid": "01951234-5678-7abc-def0-000000000002",
            "proposed_patch": {
                "nutrition_profile": {"nutri_score": "A", "kcal_per_100g": 18},
                "media_profile": {"main_image_uri": "media://tomate.png", "image_status": "uploaded"},
                "enrichment_profile": {
                    "completeness_score": 80,
                    "status": "suggested",
                    "missing_fields": ["media_profile"],
                    "last_run_uuid": "01951234-5678-7abc-def0-000000000002",
                    "last_enriched_at": "2026-05-08T10:00:00+00:00",
                },
            },
            "field_confidences": {"nutrition_profile": 0.92},
            "field_sources": {"nutrition_profile": "ciqual"},
            "reasoning_summary": "Profil V5 stable.",
        },
    )
    suggestion_uuid = suggestion_response.json()["data"]["uuid"]

    suggested_ingredient_response = await client.get(f"/v1/ingredients/{ingredient_uuid}")
    list_response = await client.get(f"/v1/ingredients/{ingredient_uuid}/enrichment-suggestions")
    apply_response = await client.post(
        f"/v1/ingredients/{ingredient_uuid}/enrichment-suggestions/{suggestion_uuid}/apply",
        json={"fields": ["nutrition_profile"], "force": False},
    )
    reject_response = await client.post(
        f"/v1/ingredients/{ingredient_uuid}/enrichment-suggestions/{suggestion_uuid}/reject",
        json={"fields": ["media_profile"]},
    )
    ingredient_response = await client.get(f"/v1/ingredients/{ingredient_uuid}")

    assert suggestion_response.status_code == 201
    assert suggested_ingredient_response.json()["data"]["enrichment_profile"]["status"] == "suggested"
    assert list_response.status_code == 200
    assert list_response.json()["data"][0]["reasoning_summary"] == "Profil V5 stable."
    assert apply_response.status_code == 200
    assert apply_response.json()["data"]["status"] == "partially_applied"
    assert reject_response.status_code == 200
    assert reject_response.json()["data"]["status"] == "partially_applied"
    assert ingredient_response.json()["data"]["nutrition_profile"]["nutri_score"] == "A"


async def test_create_enrichment_suggestion_for_missing_ingredient_returns_404(client):
    response = await client.post(
        "/v1/ingredients/01951234-5678-7abc-def0-000000000000/enrichment-suggestions",
        json={
            "run_uuid": "01951234-5678-7abc-def0-000000000002",
            "proposed_patch": {"media_profile": {"image_status": "missing"}},
        },
    )

    assert response.status_code == 404


async def test_apply_enrichment_suggestion_unknown_field_returns_409(client, created):
    ingredient_uuid = created["uuid"]
    suggestion_uuid = (await client.post(
        f"/v1/ingredients/{ingredient_uuid}/enrichment-suggestions",
        json={
            "run_uuid": "01951234-5678-7abc-def0-000000000002",
            "proposed_patch": {"media_profile": {"image_status": "missing"}},
        },
    )).json()["data"]["uuid"]

    response = await client.post(
        f"/v1/ingredients/{ingredient_uuid}/enrichment-suggestions/{suggestion_uuid}/apply",
        json={"fields": ["nutrition_profile"]},
    )

    assert response.status_code == 409


async def test_reject_missing_enrichment_suggestion_returns_404(client, created):
    response = await client.post(
        f"/v1/ingredients/{created['uuid']}/enrichment-suggestions/01951234-5678-7abc-def0-000000000003/reject",
        json={},
    )

    assert response.status_code == 404


async def test_enrichment_suggestions_without_service_return_503(service, recipe_service, logger):
    fastapi_app = FastAPI()
    fastapi_app.include_router(IngredientRouter(service, logger, recipe_service).router)
    fastapi_app.dependency_overrides[inject_tenant_uri] = lambda: None
    fastapi_app.dependency_overrides[require_auth] = lambda: {"sub": "test-user"}
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as test_client:
        response = await test_client.get(
            "/v1/ingredients/01951234-5678-7abc-def0-000000000000/enrichment-suggestions"
        )

    assert response.status_code == 503
