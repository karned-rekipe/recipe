from adapters.output.memory.repositories.ingredient_enrichment_suggestion_repository import (
    InMemoryIngredientEnrichmentSuggestionRepository,
)
from adapters.output.memory.repositories.ingredient_repository import InMemoryIngredientRepository
from application.services.ingredient_enrichment_suggestion_service import (
    IngredientEnrichmentSuggestionError,
    IngredientEnrichmentSuggestionService,
)
from domain.models.ingredient import Ingredient, MediaProfile, NutritionProfile
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


async def test_create_suggestion_marks_ingredient_as_suggested(logger):
    ingredient_repo = InMemoryIngredientRepository()
    ingredient = await ingredient_repo.create(Ingredient(name="Tomate"))
    suggestion_repo = InMemoryIngredientEnrichmentSuggestionRepository()
    service = IngredientEnrichmentSuggestionService(suggestion_repo, ingredient_repo, logger)

    await service.create(
        IngredientEnrichmentSuggestion(
            ingredient_uuid=ingredient.uuid,
            run_uuid="01951234-5678-7abc-def0-000000000002",
            proposed_patch={
                "enrichment_profile": {
                    "completeness_score": 75,
                    "status": "suggested",
                    "missing_fields": ["nutrition_profile"],
                    "last_run_uuid": "01951234-5678-7abc-def0-000000000002",
                    "last_enriched_at": "2026-05-08T10:00:00+00:00",
                },
            },
        )
    )

    updated = await ingredient_repo.read(ingredient.uuid)

    assert updated is not None
    assert updated.enrichment_profile.status == "suggested"
    assert updated.enrichment_profile.completeness_score == 75
    assert updated.enrichment_profile.missing_fields == ["nutrition_profile"]
    assert str(updated.enrichment_profile.last_run_uuid) == "01951234-5678-7abc-def0-000000000002"


async def test_create_suggestion_reuses_equivalent_pending_suggestion(logger):
    ingredient_repo = InMemoryIngredientRepository()
    ingredient = await ingredient_repo.create(Ingredient(name="Carotte"))
    suggestion_repo = InMemoryIngredientEnrichmentSuggestionRepository()
    service = IngredientEnrichmentSuggestionService(suggestion_repo, ingredient_repo, logger)
    first = await service.create(
        IngredientEnrichmentSuggestion(
            ingredient_uuid=ingredient.uuid,
            run_uuid="01951234-5678-7abc-def0-000000000002",
            proposed_patch={
                "nutrition_profile": {"nutri_score": "A", "kcal_per_100g": 41},
                "enrichment_profile": {
                    "completeness_score": 90,
                    "status": "suggested",
                    "missing_fields": ["allergen_profile"],
                    "last_run_uuid": "01951234-5678-7abc-def0-000000000002",
                    "last_enriched_at": "2026-05-08T10:00:00+00:00",
                },
            },
        )
    )

    second = await service.create(
        IngredientEnrichmentSuggestion(
            ingredient_uuid=ingredient.uuid,
            run_uuid="01951234-5678-7abc-def0-000000000003",
            proposed_patch={
                "nutrition_profile": {"nutri_score": "A", "kcal_per_100g": 41},
                "enrichment_profile": {
                    "completeness_score": 90,
                    "status": "suggested",
                    "missing_fields": ["allergen_profile"],
                    "last_run_uuid": "01951234-5678-7abc-def0-000000000003",
                    "last_enriched_at": "2026-05-08T10:05:00+00:00",
                },
            },
        )
    )
    suggestions = await suggestion_repo.find_by_ingredient_uuid(ingredient.uuid)
    updated = await ingredient_repo.read(ingredient.uuid)

    assert second.uuid == first.uuid
    assert len(suggestions) == 1
    assert updated is not None
    assert str(updated.enrichment_profile.last_run_uuid) == "01951234-5678-7abc-def0-000000000003"


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
    assert applied.applied_fields == ["media_profile"]
    assert updated is not None
    assert updated.media_profile.main_image_uri == "media://tomate.png"


async def test_apply_selected_suggestion_field_keeps_partial_status(logger):
    ingredient_repo = InMemoryIngredientRepository()
    ingredient = await ingredient_repo.create(Ingredient(name="Tomate"))
    suggestion_repo = InMemoryIngredientEnrichmentSuggestionRepository()
    service = IngredientEnrichmentSuggestionService(suggestion_repo, ingredient_repo, logger)
    suggestion = await service.create(
        IngredientEnrichmentSuggestion(
            ingredient_uuid=ingredient.uuid,
            run_uuid="01951234-5678-7abc-def0-000000000002",
            proposed_patch={
                "media_profile": {"main_image_uri": "media://tomate.png", "image_status": "uploaded"},
                "nutrition_profile": {"nutri_score": "A", "kcal_per_100g": 20},
            },
        )
    )

    applied = await service.apply(ingredient.uuid, suggestion.uuid, fields=["media_profile"])
    updated = await ingredient_repo.read(ingredient.uuid)

    assert applied.status == "partially_applied"
    assert applied.applied_fields == ["media_profile"]
    assert updated is not None
    assert updated.media_profile.main_image_uri == "media://tomate.png"
    assert updated.nutrition_profile.nutri_score == "unknown"


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
    assert applied.applied_fields == []
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
    assert rejected.rejected_fields == ["media_profile"]
    assert rejected.rejected_at is not None


async def test_reject_selected_suggestion_field_tracks_rejected_fields(logger):
    ingredient_repo = InMemoryIngredientRepository()
    ingredient = await ingredient_repo.create(Ingredient(name="Tomate"))
    suggestion_repo = InMemoryIngredientEnrichmentSuggestionRepository()
    service = IngredientEnrichmentSuggestionService(suggestion_repo, ingredient_repo, logger)
    suggestion = await service.create(
        IngredientEnrichmentSuggestion(
            ingredient_uuid=ingredient.uuid,
            run_uuid="01951234-5678-7abc-def0-000000000002",
            proposed_patch={
                "media_profile": {"image_status": "missing"},
                "nutrition_profile": NutritionProfile(nutri_score="A").model_dump(mode="python"),
            },
        )
    )

    rejected = await service.reject(ingredient.uuid, suggestion.uuid, fields=["nutrition_profile"])
    updated = await ingredient_repo.read(ingredient.uuid)

    assert rejected.status == "partially_applied"
    assert rejected.rejected_fields == ["nutrition_profile"]
    assert rejected.rejected_at is None
    assert updated is not None
    assert updated.enrichment_profile.rejected_fields == ["nutrition_profile"]
