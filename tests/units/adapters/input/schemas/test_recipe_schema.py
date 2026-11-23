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

INGREDIENT_UUID = "01951234-5678-7abc-def0-000000000101"
EQUIPMENT_UUID = "01951234-5678-7abc-def0-000000000102"


def _payload(**kwargs) -> dict:
    payload = {
        "name": "Farine",
        "servings": 4,
        "ingredients": [{
            "ingredient_uuid": INGREDIENT_UUID,
            "quantity": 500,
            "unit": "g",
        }],
        "equipment": [{"equipment_uuid": EQUIPMENT_UUID, "quantity": 1}],
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
    s = RecipeCreateSchema(**_payload(subtitle="Tarte citron meringuée"))
    assert s.name == "Farine"
    assert s.subtitle == "Tarte citron meringuée"
    assert s.servings == 4
    assert len(s.ingredients) == 1
    assert len(s.steps) == 1

    recipe = recipe_create_payload_to_domain(s)
    assert recipe.subtitle == "Tarte citron meringuée"


def test_create_schema_accepts_components():
    child_uuid = "01951234-5678-7abc-def0-000000000201"
    s = RecipeCreateSchema(
        **_payload(
            components=[{
                "recipe_uuid": child_uuid,
                "label": "Crème anglaise",
                "rank": 1,
                "servings_multiplier": 2,
            }]
        )
    )
    recipe = recipe_create_payload_to_domain(s)

    assert len(recipe.components) == 1
    assert str(recipe.components[0].recipe_uuid) == child_uuid
    assert recipe.components[0].label == "Crème anglaise"
    assert recipe.components[0].servings_multiplier == 2


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


def test_create_schema_allows_empty_ingredients_and_steps():
    schema = RecipeCreateSchema(**_payload(ingredients=[], steps=[]))
    recipe = recipe_create_payload_to_domain(schema)
    assert recipe.ingredients == []
    assert recipe.steps == []
    assert recipe.status == RecipeStatus.draft


def test_patch_schema_all_none():
    s = RecipePatchSchema()
    assert s.name is None
    assert s.ingredients is None


def test_patch_schema_partial():
    s = RecipePatchSchema(name="Farine complete", subtitle="Farine de caractère")
    assert s.name == "Farine complete"
    assert s.subtitle == "Farine de caractère"


def test_patch_payload_can_clear_subtitle():
    existing = Recipe(name="Farine", subtitle="Farine de caractère")

    patched = recipe_patch_payload_to_domain(existing, RecipePatchSchema(subtitle=None))

    assert patched.subtitle is None


def test_patch_schema_null_collection_raises():
    with pytest.raises(Exception):
        RecipePatchSchema(ingredients=None)


def test_update_schema_valid():
    s = RecipeUpdateSchema(**_payload(name="Sel fin"))
    assert s.name == "Sel fin"


def test_update_payload_generates_component_uuid_when_omitted():
    child_uuid = "01951234-5678-7abc-def0-000000000201"
    existing = Recipe(name="Farine", servings=4)
    payload = RecipeUpdateSchema(
        **_payload(
            components=[{
                "recipe_uuid": child_uuid,
                "label": "Crème anglaise",
                "rank": 1,
            }]
        )
    )

    updated = recipe_update_payload_to_domain(existing, payload)

    assert len(updated.components) == 1
    assert updated.components[0].uuid is not None
    assert str(updated.components[0].recipe_uuid) == child_uuid


def test_patch_payload_generates_component_uuid_when_omitted():
    child_uuid = "01951234-5678-7abc-def0-000000000201"
    existing = Recipe(name="Farine", servings=4)
    payload = RecipePatchSchema(
        components=[{
            "recipe_uuid": child_uuid,
            "label": "Crème anglaise",
            "rank": 1,
        }]
    )

    updated = recipe_patch_payload_to_domain(existing, payload)

    assert len(updated.components) == 1
    assert updated.components[0].uuid is not None
    assert str(updated.components[0].recipe_uuid) == child_uuid


def test_recipe_schema_from_entity():
    entity = Recipe(
        name="Farine",
        subtitle="Farine de caractère",
        servings=4,
        favorite=True,
        legacy_id=42,
        quality_status=RecipeQualityStatus.validated,
        migration_metadata={"source_table": "mkg_recipe"},
        ingredients=[RecipeIngredient(ingredient_uuid=INGREDIENT_UUID, quantity=500, unit="g")],
        equipment=[RecipeEquipment(equipment_uuid=EQUIPMENT_UUID, quantity=1)],
        steps=[Step(name="Melanger", rank=1)],
    )
    payload = entity.model_dump(mode="json")
    payload["is_deleted"] = entity.is_deleted
    payload["ingredients"] = [{
        "ingredient_uuid": INGREDIENT_UUID,
        "name": "Farine de ble",
        "quantity": 500,
        "unit": "g",
        "season_months": {},
        "rayon": None,
        "group": None,
        "green_score": 80,
    }]
    payload["equipment"] = [{"equipment_uuid": EQUIPMENT_UUID, "name": "Saladier", "quantity": 1}]
    schema = RecipeSchema.model_validate(payload)
    assert schema.name == "Farine"
    assert schema.subtitle == "Farine de caractère"
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
        ingredients=[RecipeIngredient(ingredient_uuid=INGREDIENT_UUID, quantity=500, unit="g")],
        equipment=[RecipeEquipment(equipment_uuid=EQUIPMENT_UUID, quantity=1)],
        steps=[Step(name="Melanger", rank=1)],
    )
    patched = recipe_patch_payload_to_domain(
        existing,
        RecipePatchSchema(ingredients=[{
            "ingredient_uuid": INGREDIENT_UUID,
            "quantity": 450,
            "unit": "g",
        }]),
    )
    assert patched.name == "Farine"
    assert str(patched.ingredients[0].ingredient_uuid) == INGREDIENT_UUID
    assert patched.ingredients[0].quantity == 450
    assert str(patched.equipment[0].equipment_uuid) == EQUIPMENT_UUID
    assert patched.steps[0].name == "Melanger"
    assert patched.legacy_id == 42
    assert patched.status == RecipeStatus.active
    assert patched.quality_status == RecipeQualityStatus.text_only
    assert patched.migration_metadata == {"source_table": "mkg_recipe"}


def test_update_payload_to_domain_preserves_unset_migration_metadata():
    existing = Recipe(
        name="Farine",
        subtitle="Farine de caractère",
        servings=4,
        favorite=True,
        legacy_id=42,
        status=RecipeStatus.archived,
        quality_status=RecipeQualityStatus.text_only,
        migration_metadata={"source_table": "mkg_recipe"},
        ingredients=[RecipeIngredient(ingredient_uuid=INGREDIENT_UUID, quantity=500, unit="g")],
        equipment=[RecipeEquipment(equipment_uuid=EQUIPMENT_UUID, quantity=1)],
        steps=[Step(name="Melanger", rank=1)],
    )

    updated = recipe_update_payload_to_domain(existing, RecipeUpdateSchema(**_payload(name="Farine T80")))

    assert updated.name == "Farine T80"
    assert updated.subtitle == "Farine de caractère"
    assert updated.favorite is True
    assert updated.legacy_id == 42
    assert updated.status == RecipeStatus.active
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
