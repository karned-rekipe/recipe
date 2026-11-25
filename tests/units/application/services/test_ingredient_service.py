import pytest
from unittest.mock import AsyncMock

from adapters.output.memory.repositories.ingredient_repository import InMemoryIngredientRepository
from application.services.ingredient_service import (
    IngredientImageGenerationUnavailableError,
    IngredientService,
)
from domain.models.ingredient import Ingredient
from domain.models.ingredient_ai_enrichment import IngredientAIEnrichment
from domain.models.ingredient_image_generation import IngredientImageGeneration
from domain.ports.output.ingredient_image_generation_agent import IngredientImageGenerationAgent

GROUP_UUID = "01951234-5678-7abc-def0-000000000201"
RAYON_UUID = "01951234-5678-7abc-def0-000000000202"


@pytest.fixture
def ingredient_repo():
    return InMemoryIngredientRepository()


@pytest.fixture
def service(ingredient_repo, logger):
    return IngredientService(ingredient_repo, logger)


async def test_create_and_read(service):
    ingredient = await service.create(Ingredient(name="Tomate"))
    found = await service.read(ingredient.uuid)
    assert found is not None
    assert found.name == "Tomate"


async def test_create_with_all_fields(service):
    ingredient = await service.create(Ingredient(
        name="Tomate",
        rayon_uuid=RAYON_UUID,
        group_uuid=GROUP_UUID,
        green_score=80,
        unit="g",
        quantity=100.0,
        season_months={7: 3, 8: 3},
    ))
    found = await service.read(ingredient.uuid)
    assert found is not None
    assert str(found.rayon_uuid) == RAYON_UUID
    assert found.season_months == {7: 3, 8: 3}


async def test_update(service):
    ingredient = await service.create(Ingredient(name="Tomate"))
    updated = await service.update(ingredient.model_copy(update={"name": "Tomate cerise"}))
    assert updated.name == "Tomate cerise"
    assert updated.version == 2


async def test_delete_hides_from_read(service):
    ingredient = await service.create(Ingredient(name="Sel"))
    await service.delete(ingredient.uuid)
    assert await service.read(ingredient.uuid) is None


async def test_find_all(service):
    await service.create(Ingredient(name="Tomate"))
    await service.create(Ingredient(name="Carotte"))
    result = await service.find_all()
    assert len(result) == 2


async def test_find_by_name(service):
    await service.create(Ingredient(name="Tomate cerise"))
    await service.create(Ingredient(name="Carotte"))
    result = await service.find_by_name("tomate")
    assert len(result) == 1
    assert result[0].name == "Tomate cerise"


async def test_duplicate(service):
    ingredient = await service.create(Ingredient(name="Tomate", season_months={7: 3}))
    clone = await service.duplicate(ingredient.uuid)
    assert clone.uuid != ingredient.uuid
    assert clone.name == ingredient.name
    assert clone.season_months == ingredient.season_months


async def test_find_page_filtered_no_filter(service):
    await service.create(Ingredient(name="Tomate"))
    await service.create(Ingredient(name="Carotte"))
    items, total = await service.find_page_filtered(offset=0, limit=10)
    assert total == 2
    assert len(items) == 2


async def test_find_page_filtered_with_name(service):
    await service.create(Ingredient(name="Tomate cerise"))
    await service.create(Ingredient(name="Carotte"))
    items, total = await service.find_page_filtered(name="tomate", offset=0, limit=10)
    assert total == 1
    assert items[0].name == "Tomate cerise"


async def test_convert_unit_uses_global_registry(service):
    ingredient = await service.create(Ingredient(name="Farine"))

    result = await service.convert_unit(ingredient.uuid, 1.5, "kg", "g")

    assert result["converted_quantity"] == 1500
    assert result["source"] == "global"


async def test_list_units_contains_shopping_purchase_units(service):
    units = await service.list_units()
    codes = {unit["code"] for unit in units}

    assert {"paquet", "boite", "bouteille", "barquette"}.issubset(codes)


async def test_generate_main_image_suggestion_uses_internal_agent(ingredient_repo, logger):
    agent = AsyncMock(spec=IngredientImageGenerationAgent)
    service = IngredientService(
        ingredient_repo,
        logger,
        image_generation_agent=agent,
    )
    ingredient = await service.create(Ingredient(name="Carotte"))
    agent.generate.return_value = IngredientImageGeneration(
        run_uuid="01951234-5678-7abc-def0-000000000301",
        ingredient_uuid=str(ingredient.uuid),
        suggestion_uuid="01951234-5678-7abc-def0-000000000302",
        status="success",
        completeness_score=25,
        missing_fields=["media_profile"],
        proposed_fields=["media_profile"],
    )

    result = await service.generate_main_image_suggestion(ingredient.uuid)

    assert result.suggestion_uuid == "01951234-5678-7abc-def0-000000000302"
    agent.generate.assert_awaited_once_with(ingredient_uuid=str(ingredient.uuid))


async def test_generate_main_image_suggestion_requires_configured_agent(
    ingredient_repo,
    logger,
):
    service = IngredientService(ingredient_repo, logger)
    ingredient = await service.create(Ingredient(name="Carotte"))

    with pytest.raises(IngredientImageGenerationUnavailableError):
        await service.generate_main_image_suggestion(ingredient.uuid)


async def test_complete_with_ai_uses_internal_agent(ingredient_repo, logger):
    agent = AsyncMock(spec=IngredientImageGenerationAgent)
    service = IngredientService(
        ingredient_repo,
        logger,
        enrichment_agent=agent,
    )
    ingredient = await service.create(Ingredient(name="Carotte"))
    agent.complete.return_value = IngredientAIEnrichment(
        run_uuid="01951234-5678-7abc-def0-000000000311",
        ingredient_uuid=str(ingredient.uuid),
        suggestion_uuid="01951234-5678-7abc-def0-000000000312",
        status="success",
        completeness_score=25,
        missing_fields=["media_profile", "nutrition_profile"],
        proposed_fields=["media_profile", "nutrition_profile"],
        image_generated=True,
    )

    result = await service.complete_with_ai(ingredient.uuid)

    assert result.image_generated is True
    agent.complete.assert_awaited_once_with(ingredient_uuid=str(ingredient.uuid))


async def test_generate_main_image_suggestion_rejects_mismatched_result(
    ingredient_repo,
    logger,
):
    agent = AsyncMock(spec=IngredientImageGenerationAgent)
    service = IngredientService(
        ingredient_repo,
        logger,
        image_generation_agent=agent,
    )
    ingredient = await service.create(Ingredient(name="Carotte"))
    agent.generate.return_value = IngredientImageGeneration(
        run_uuid="01951234-5678-7abc-def0-000000000301",
        ingredient_uuid="01951234-5678-7abc-def0-000000000399",
        suggestion_uuid="01951234-5678-7abc-def0-000000000302",
        status="success",
        completeness_score=25,
        missing_fields=["media_profile"],
        proposed_fields=["media_profile"],
    )

    with pytest.raises(RuntimeError, match="another ingredient"):
        await service.generate_main_image_suggestion(ingredient.uuid)
