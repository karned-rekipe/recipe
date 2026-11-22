import asyncio
from unittest.mock import AsyncMock

import pytest
from uuid6 import uuid7

from application.services.recipe_service import (
    RecipeComponentCycleError,
    RecipeComponentInUseError,
    RecipeImageAlreadyExistsError,
    RecipeImageGenerationInProgressError,
    RecipeImageGenerationUnavailableError,
    RecipeAIEnrichmentUnavailableError,
    RecipeService,
)
from domain.models.generated_recipe_image import GeneratedRecipeImage
from domain.models.recipe_ai_enrichment import RecipeAIEnrichment
from domain.models.recipe import Recipe
from domain.models.recipe_component import RecipeComponent
from domain.models.recipe_ingredient import RecipeIngredient
from domain.models.recipe_line_origin import RecipeLineOrigin
from domain.models.step import Step
from domain.ports.output.recipe_image_generator import RecipeImageGenerator
from domain.ports.output.recipe_ai_enrichment_agent import RecipeAIEnrichmentAgent


@pytest.fixture
def service(repo, logger):
    return RecipeService(repo, logger)


async def test_create_and_read(service):
    recipe = await service.create(Recipe(name="Farine"))
    found = await service.read(recipe.uuid)
    assert found is not None
    assert found.name == "Farine"


async def test_update(service):
    recipe = await service.create(Recipe(name="Farine"))
    updated = await service.update(recipe.model_copy(update={"name": "Farine complète"}))
    assert updated.name == "Farine complète"
    assert updated.version == 2


async def test_delete_hides_from_read(service):
    recipe = await service.create(Recipe(name="Sel"))
    await service.delete(recipe.uuid)
    assert await service.read(recipe.uuid) is None


async def test_find_all(service):
    await service.create(Recipe(name="Farine"))
    await service.create(Recipe(name="Sel"))
    result = await service.find_all()
    assert len(result) == 2


async def test_find_by_name(service):
    await service.create(Recipe(name="Farine de blé"))
    await service.create(Recipe(name="Sel fin"))
    result = await service.find_by_name("farine")
    assert len(result) == 1
    assert result[0].name == "Farine de blé"


async def test_duplicate(service):
    recipe = await service.create(Recipe(name="Farine"))
    clone = await service.duplicate(recipe.uuid)
    assert clone.uuid != recipe.uuid
    assert clone.name == "Farine"


async def test_read_unknown_returns_none(service):
    assert await service.read(uuid7()) is None


async def test_generate_main_image_requires_configured_generator(repo, logger):
    recipe = await RecipeService(repo, logger).create(Recipe(name="Soupe"))

    with pytest.raises(RecipeImageGenerationUnavailableError):
        await RecipeService(repo, logger).generate_main_image(recipe.uuid)


async def test_enrich_with_ai_requires_configured_agent(repo, logger):
    recipe = await RecipeService(repo, logger).create(Recipe(name="Soupe"))

    with pytest.raises(RecipeAIEnrichmentUnavailableError):
        await RecipeService(repo, logger).enrich_with_ai(recipe.uuid)


async def test_enrich_with_ai_delegates_to_internal_agent(repo, logger):
    agent = AsyncMock(spec=RecipeAIEnrichmentAgent)
    agent.enrich.return_value = RecipeAIEnrichment(
        recipe_uuid="placeholder",
        recipe_name="Soupe",
        formatted_response="Recette enrichie",
        updated=True,
    )
    service = RecipeService(repo, logger, ai_enrichment_agent=agent)
    recipe = await service.create(Recipe(name="Soupe"))

    updated, result = await service.enrich_with_ai(recipe.uuid, generate_image=False)

    assert updated.uuid == recipe.uuid
    assert result.updated is True
    agent.enrich.assert_awaited_once_with(
        recipe_uuid=str(recipe.uuid),
        generate_image=False,
    )


async def test_generate_main_image_refuses_implicit_replacement(repo, logger):
    generator = AsyncMock(spec=RecipeImageGenerator)
    service = RecipeService(repo, logger, image_generator=generator)
    recipe = await service.create(Recipe(name="Soupe", main_image="/existing.png"))

    with pytest.raises(RecipeImageAlreadyExistsError):
        await service.generate_main_image(recipe.uuid)

    generator.generate.assert_not_awaited()


async def test_generate_main_image_persists_generated_url(repo, logger):
    generator = AsyncMock(spec=RecipeImageGenerator)
    generator.generate.return_value = GeneratedRecipeImage.model_validate({
        "image": {
            "bucket": "recipes",
            "key": "recipes/soupe.png",
            "url": "/api/media/v1/buckets/recipes/objects/recipes/soupe.png",
            "content_type": "image/png",
            "size_bytes": 42,
        },
        "provider": "test",
    })
    service = RecipeService(repo, logger, image_generator=generator)
    recipe = await service.create(Recipe(name="Soupe"))

    updated, generated = await service.generate_main_image(recipe.uuid)

    assert updated.main_image == generated.image.url
    assert (await service.read(recipe.uuid)).main_image == generated.image.url


async def test_generate_main_image_reserves_recipe_against_duplicate_requests(repo, logger):
    started = asyncio.Event()
    finish = asyncio.Event()
    generated = GeneratedRecipeImage.model_validate({
        "image": {
            "bucket": "recipes",
            "key": "recipes/soupe.png",
            "url": "/api/media/v1/buckets/recipes/objects/recipes/soupe.png",
            "content_type": "image/png",
            "size_bytes": 42,
        },
        "provider": "test",
    })

    async def generate_once(**_kwargs):
        started.set()
        await finish.wait()
        return generated

    generator = AsyncMock(spec=RecipeImageGenerator)
    generator.generate.side_effect = generate_once
    service = RecipeService(repo, logger, image_generator=generator)
    recipe = await service.create(Recipe(name="Soupe"))

    first = asyncio.create_task(service.generate_main_image(recipe.uuid))
    await started.wait()
    with pytest.raises(RecipeImageGenerationInProgressError):
        await service.generate_main_image(recipe.uuid)
    finish.set()
    await first

    assert generator.generate.await_count == 1


async def test_generate_main_image_preserves_concurrent_recipe_edits(repo, logger):
    started = asyncio.Event()
    finish = asyncio.Event()
    generated = GeneratedRecipeImage.model_validate({
        "image": {
            "bucket": "recipes",
            "key": "recipes/soupe.png",
            "url": "/api/media/v1/buckets/recipes/objects/recipes/soupe.png",
            "content_type": "image/png",
            "size_bytes": 42,
        },
        "provider": "test",
    })

    async def generate_after_edit(**_kwargs):
        started.set()
        await finish.wait()
        return generated

    generator = AsyncMock(spec=RecipeImageGenerator)
    generator.generate.side_effect = generate_after_edit
    service = RecipeService(repo, logger, image_generator=generator)
    recipe = await service.create(Recipe(name="Soupe"))

    generation = asyncio.create_task(service.generate_main_image(recipe.uuid))
    await started.wait()
    await service.update(recipe.model_copy(update={"name": "Soupe paysanne"}))
    finish.set()
    updated, _ = await generation

    assert updated.name == "Soupe paysanne"
    assert updated.main_image == generated.image.url


async def test_find_by_name_no_results(service):
    await service.create(Recipe(name="Sel"))
    result = await service.find_by_name("farine")
    assert result == []


async def test_find_page_filtered_by_main_image(service):
    await service.create(Recipe(name="Sans image"))
    await service.create(Recipe(name="Avec image", main_image="https://example.com/recipe.jpg"))

    items, total = await service.find_page_filtered(has_main_image=False)

    assert total == 1
    assert [item.name for item in items] == ["Sans image"]


async def test_create_parent_projects_component_lines(service):
    ingredient_uuid = uuid7()
    child = await service.create(
        Recipe(
            name="Crème anglaise",
            ingredients=[RecipeIngredient(ingredient_uuid=ingredient_uuid, quantity=250, unit="ml")],
            steps=[Step(name="Cuire la crème", rank=1)],
        )
    )

    parent = await service.create(
        Recipe(
            name="Île flottante",
            components=[
                RecipeComponent(
                    recipe_uuid=child.uuid,
                    label="Crème anglaise",
                    rank=1,
                    servings_multiplier=2,
                )
            ],
        )
    )

    assert parent.status == "active"
    assert parent.ingredients[0].ingredient_uuid == ingredient_uuid
    assert parent.ingredients[0].quantity == 500
    assert parent.ingredients[0].line_origin == RecipeLineOrigin.component_projection
    assert parent.ingredients[0].source_recipe_uuid == child.uuid
    assert parent.steps[0].name == "Cuire la crème"
    assert parent.steps[0].line_origin == RecipeLineOrigin.component_projection


async def test_update_child_propagates_projection_to_parent(service):
    ingredient_uuid = uuid7()
    child = await service.create(
        Recipe(
            name="Meringue",
            ingredients=[RecipeIngredient(ingredient_uuid=ingredient_uuid, quantity=50, unit="g")],
        )
    )
    parent = await service.create(
        Recipe(
            name="Île flottante",
            components=[RecipeComponent(recipe_uuid=child.uuid, label="Meringue", rank=1, servings_multiplier=3)],
        )
    )

    await service.update(
        child.model_copy(
            update={
                "ingredients": [
                    RecipeIngredient(ingredient_uuid=ingredient_uuid, quantity=70, unit="g"),
                ]
            }
        )
    )
    updated_parent = await service.read(parent.uuid)

    assert updated_parent is not None
    assert updated_parent.version == parent.version + 1
    assert updated_parent.ingredients[0].quantity == 210


async def test_component_cycle_is_rejected(service):
    child = await service.create(Recipe(name="Caramel"))
    parent = await service.create(
        Recipe(
            name="Île flottante",
            components=[RecipeComponent(recipe_uuid=child.uuid, label="Caramel", rank=1)],
        )
    )

    with pytest.raises(RecipeComponentCycleError):
        await service.update(
            child.model_copy(
                update={"components": [RecipeComponent(recipe_uuid=parent.uuid, label="Parent", rank=1)]}
            )
        )


async def test_delete_component_in_use_is_rejected(service):
    child = await service.create(Recipe(name="Caramel"))
    await service.create(
        Recipe(
            name="Île flottante",
            components=[RecipeComponent(recipe_uuid=child.uuid, label="Caramel", rank=1)],
        )
    )

    with pytest.raises(RecipeComponentInUseError):
        await service.delete(child.uuid)
