from datetime import datetime, timezone

import pytest

from adapters.input.schemas.recipe_schema import (
    RecipeCreateSchema,
    RecipePatchSchema,
    RecipeSchema,
    RecipeUpdateSchema,
    recipe_create_payload_to_domain,
    recipe_patch_payload_to_domain,
    recipe_update_payload_to_domain,
)
from domain.models.recipe import Recipe, RecipeQualityStatus, RecipeStatus
from domain.models.recipe_equipment import RecipeEquipment
from domain.models.recipe_ingredient import RecipeIngredient
from domain.models.step import Step


def _payload(**kwargs) -> dict:
    payload = {
        "name": "Farine",
        "servings": 4,
        "ingredients": [{
            "name": "Farine de ble",
            "quantity": 500,
            "unit": "g",
            "season_months": {},
        }],
        "equipment": [{"name": "Saladier", "quantity": 1}],
        "steps": [{
            "name": "Melanger",
            "description": "Melanger les ingredients.",
            "rank": 1,
            "secondary_images": [],
        }],
        "sources": [],
        "secondary_images": [],
    }
    payload.update(kwargs)
    return payload


def test_create_schema_valid():
    s = RecipeCreateSchema(**_payload())
    assert s.name == "Farine"
    assert s.servings == 4
    assert len(s.ingredients) == 1
    assert len(s.steps) == 1


def test_create_payload_to_domain_maps_migration_metadata():
    payload = RecipeCreateSchema(
        **_payload(
            favorite=True,
            status="archived",
            quality_status="text_only",
            legacy_id=42,
            migration_metadata={"source_table": "mkg_recipe", "imported": True},
        )
    )
    recipe = recipe_create_payload_to_domain(payload)

    assert recipe.favorite is True
    assert recipe.status == RecipeStatus.archived
    assert recipe.quality_status == RecipeQualityStatus.text_only
    assert recipe.legacy_id == 42
    assert recipe.migration_metadata == {"source_table": "mkg_recipe", "imported": True}


def test_create_schema_missing_servings_raises():
    payload = _payload()
    payload.pop("servings")
    with pytest.raises(Exception):
        RecipeCreateSchema(**payload)


def test_create_schema_requires_ingredient_and_step():
    with pytest.raises(Exception):
        RecipeCreateSchema(**_payload(ingredients=[]))
    with pytest.raises(Exception):
        RecipeCreateSchema(**_payload(steps=[]))


def test_patch_schema_all_none():
    s = RecipePatchSchema()
    assert s.name is None
    assert s.ingredients is None


def test_patch_schema_partial():
    s = RecipePatchSchema(name="Farine complete")
    assert s.name == "Farine complete"


def test_patch_schema_null_collection_raises():
    with pytest.raises(Exception):
        RecipePatchSchema(ingredients=None)


def test_update_schema_valid():
    s = RecipeUpdateSchema(**_payload(name="Sel fin"))
    assert s.name == "Sel fin"


def test_recipe_schema_from_entity():
    entity = Recipe(
        name="Farine",
        servings=4,
        favorite=True,
        legacy_id=42,
        quality_status=RecipeQualityStatus.validated,
        migration_metadata={"source_table": "mkg_recipe"},
        ingredients=[RecipeIngredient(name="Farine de ble", quantity=500, unit="g", season_months={})],
        equipment=[RecipeEquipment(name="Saladier", quantity=1)],
        steps=[Step(name="Melanger", rank=1)],
    )
    schema = RecipeSchema.model_validate(entity)
    assert schema.name == "Farine"
    assert schema.ingredients[0].name == "Farine de ble"
    assert schema.equipment[0].name == "Saladier"
    assert schema.steps[0].name == "Melanger"
    assert schema.favorite is True
    assert schema.legacy_id == 42
    assert schema.quality_status == RecipeQualityStatus.validated
    assert schema.migration_metadata == {"source_table": "mkg_recipe"}
    assert schema.is_deleted is False
    assert schema.version == 1


def test_recipe_schema_deleted_entity():
    entity = Recipe(name="Sel", deleted_at=datetime.now(timezone.utc))
    schema = RecipeSchema.model_validate(entity)
    assert schema.is_deleted is True


def test_recipe_schema_uuid_serialized():
    entity = Recipe(name="Farine")
    schema = RecipeSchema.model_validate(entity)
    assert str(schema.uuid) == str(entity.uuid)


def test_patch_payload_to_domain_preserves_unset_sections():
    existing = Recipe(
        name="Farine",
        servings=4,
        legacy_id=42,
        status=RecipeStatus.archived,
        quality_status=RecipeQualityStatus.text_only,
        migration_metadata={"source_table": "mkg_recipe"},
        ingredients=[RecipeIngredient(name="Farine de ble", quantity=500, unit="g", season_months={})],
        equipment=[RecipeEquipment(name="Saladier", quantity=1)],
        steps=[Step(name="Melanger", rank=1)],
    )
    patched = recipe_patch_payload_to_domain(
        existing,
        RecipePatchSchema(ingredients=[{
            "name": "Farine T80",
            "quantity": 450,
            "unit": "g",
            "season_months": {},
        }]),
    )
    assert patched.name == "Farine"
    assert patched.ingredients[0].name == "Farine T80"
    assert patched.equipment[0].name == "Saladier"
    assert patched.steps[0].name == "Melanger"
    assert patched.legacy_id == 42
    assert patched.status == RecipeStatus.archived
    assert patched.quality_status == RecipeQualityStatus.text_only
    assert patched.migration_metadata == {"source_table": "mkg_recipe"}


def test_update_payload_to_domain_preserves_unset_migration_metadata():
    existing = Recipe(
        name="Farine",
        servings=4,
        favorite=True,
        legacy_id=42,
        status=RecipeStatus.archived,
        quality_status=RecipeQualityStatus.text_only,
        migration_metadata={"source_table": "mkg_recipe"},
        ingredients=[RecipeIngredient(name="Farine de ble", quantity=500, unit="g", season_months={})],
        equipment=[RecipeEquipment(name="Saladier", quantity=1)],
        steps=[Step(name="Melanger", rank=1)],
    )

    updated = recipe_update_payload_to_domain(existing, RecipeUpdateSchema(**_payload(name="Farine T80")))

    assert updated.name == "Farine T80"
    assert updated.favorite is True
    assert updated.legacy_id == 42
    assert updated.status == RecipeStatus.archived
    assert updated.quality_status == RecipeQualityStatus.text_only
    assert updated.migration_metadata == {"source_table": "mkg_recipe"}


def test_patch_payload_to_domain_can_update_migration_metadata():
    existing = Recipe(name="Farine", migration_metadata={"source_table": "mkg_recipe"})
    patched = recipe_patch_payload_to_domain(
        existing,
        RecipePatchSchema(
            quality_status="validated",
            migration_metadata={"source_table": "mkg_recipe", "qc_passed": True},
        ),
    )

    assert patched.quality_status == RecipeQualityStatus.validated
    assert patched.migration_metadata == {"source_table": "mkg_recipe", "qc_passed": True}


def test_patch_schema_null_migration_metadata_raises():
    with pytest.raises(Exception):
        RecipePatchSchema(migration_metadata=None)
