from adapters.output.memory.repositories.ingredient_enrichment_suggestion_repository import (
    InMemoryIngredientEnrichmentSuggestionRepository,
)
from adapters.output.memory.repositories.ingredient_repository import InMemoryIngredientRepository
from application.services.ingredient_enrichment_suggestion_service import (
    IngredientEnrichmentSuggestionError,
    IngredientEnrichmentSuggestionService,
)
from domain.models.ingredient import Ingredient, MediaProfile
from domain.models.ingredient_enrichment_suggestion import IngredientEnrichmentSuggestion


async def test_create_suggestion_requires_existing_ingredient(logger):
    ingredient_repo = InMemoryIngredientRepository()
    service = IngredientEnrichmentSuggestionService(
        InMemoryIngredientEnrichmentSuggestionRepository(),
        ingredient_repo,
        logger,
    )

    try:
        await service.create(
            IngredientEnrichmentSuggestion(
                ingredient_uuid="01951234-5678-7abc-def0-000000000001",
                run_uuid="01951234-5678-7abc-def0-000000000002",
            )
        )
    except IngredientEnrichmentSuggestionError as exc:
        assert "Ingredient not found" in str(exc)
    else:
        raise AssertionError("Expected missing ingredient to fail")


async def test_apply_suggestion_updates_unvalidated_profile(logger):
    ingredient_repo = InMemoryIngredientRepository()
    ingredient = await ingredient_repo.create(Ingredient(name="Tomate"))
    suggestion_repo = InMemoryIngredientEnrichmentSuggestionRepository()
    service = IngredientEnrichmentSuggestionService(suggestion_repo, ingredient_repo, logger)
    suggestion = await service.create(
        IngredientEnrichmentSuggestion(
            ingredient_uuid=ingredient.uuid,
            run_uuid="01951234-5678-7abc-def0-000000000002",
            proposed_patch={"media_profile": {"main_image_uri": "media://tomate.png", "image_status": "uploaded"}},
        )
    )

    applied = await service.apply(ingredient.uuid, suggestion.uuid)
    updated = await ingredient_repo.read(ingredient.uuid)

    assert applied.status == "applied"
    assert updated is not None
    assert updated.media_profile.main_image_uri == "media://tomate.png"


async def test_apply_suggestion_does_not_overwrite_validated_profile_without_force(logger):
    ingredient_repo = InMemoryIngredientRepository()
    ingredient = await ingredient_repo.create(
        Ingredient(
            name="Tomate",
            media_profile=MediaProfile(main_image_uri="media://manual.png", image_status="uploaded", validated=True),
        )
    )
    suggestion_repo = InMemoryIngredientEnrichmentSuggestionRepository()
    service = IngredientEnrichmentSuggestionService(suggestion_repo, ingredient_repo, logger)
    suggestion = await service.create(
        IngredientEnrichmentSuggestion(
            ingredient_uuid=ingredient.uuid,
            run_uuid="01951234-5678-7abc-def0-000000000002",
            proposed_patch={"media_profile": {"main_image_uri": "media://ai.png", "image_status": "generated"}},
        )
    )

    applied = await service.apply(ingredient.uuid, suggestion.uuid)
    updated = await ingredient_repo.read(ingredient.uuid)

    assert applied.status == "partially_applied"
    assert updated is not None
    assert updated.media_profile.main_image_uri == "media://manual.png"


async def test_reject_suggestion_sets_rejected_status(logger):
    ingredient_repo = InMemoryIngredientRepository()
    ingredient = await ingredient_repo.create(Ingredient(name="Tomate"))
    suggestion_repo = InMemoryIngredientEnrichmentSuggestionRepository()
    service = IngredientEnrichmentSuggestionService(suggestion_repo, ingredient_repo, logger)
    suggestion = await service.create(
        IngredientEnrichmentSuggestion(
            ingredient_uuid=ingredient.uuid,
            run_uuid="01951234-5678-7abc-def0-000000000002",
            proposed_patch={"media_profile": {"image_status": "missing"}},
        )
    )

    rejected = await service.reject(ingredient.uuid, suggestion.uuid)

    assert rejected.status == "rejected"
    assert rejected.rejected_at is not None
