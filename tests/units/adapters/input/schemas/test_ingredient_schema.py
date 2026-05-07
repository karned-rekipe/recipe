import pytest

from adapters.input.schemas.ingredient_schema import (
    IngredientCreateSchema,
    IngredientPatchSchema,
    IngredientSchema,
    IngredientUpdateSchema,
)
from domain.models.ingredient import Ingredient

GROUP_UUID = "01951234-5678-7abc-def0-000000000201"
RAYON_UUID = "01951234-5678-7abc-def0-000000000202"
SUPPLIER_UUID = "01951234-5678-7abc-def0-000000000203"
SECONDARY_SUPPLIER_UUID = "01951234-5678-7abc-def0-000000000204"


# --- IngredientCreateSchema ---

def test_create_schema_valid():
    s = IngredientCreateSchema(name="Tomate")
    assert s.name == "Tomate"


def test_create_schema_empty_name_raises():
    with pytest.raises(Exception):
        IngredientCreateSchema(name="")


def test_create_schema_season_months_valid():
    s = IngredientCreateSchema(name="Tomate", season_months={7: 3, 8: 3})
    assert s.season_months == {7: 3, 8: 3}


def test_create_schema_season_months_invalid_month_raises():
    with pytest.raises(Exception):
        IngredientCreateSchema(name="Tomate", season_months={13: 2})


def test_create_schema_season_months_invalid_score_raises():
    with pytest.raises(Exception):
        IngredientCreateSchema(name="Tomate", season_months={7: 4})


def test_create_schema_all_fields():
    s = IngredientCreateSchema(
        name="Tomate",
        rayon_uuid=RAYON_UUID,
        group_uuid=GROUP_UUID,
        main_supplier_uuid=SUPPLIER_UUID,
        secondary_supplier_uuids=[SECONDARY_SUPPLIER_UUID],
        green_score=80,
        unit="g",
        quantity=100.0,
        season_months={7: 3},
    )
    assert str(s.rayon_uuid) == RAYON_UUID
    assert str(s.group_uuid) == GROUP_UUID
    assert str(s.main_supplier_uuid) == SUPPLIER_UUID
    assert [str(uuid) for uuid in s.secondary_supplier_uuids] == [SECONDARY_SUPPLIER_UUID]
    assert s.green_score == 80
    assert s.unit == "g"
    assert s.quantity == 100.0


# --- IngredientPatchSchema ---

def test_patch_schema_all_none():
    s = IngredientPatchSchema()
    assert s.name is None
    assert s.rayon_uuid is None
    assert s.main_supplier_uuid is None
    assert s.secondary_supplier_uuids is None
    assert s.season_months is None


def test_patch_schema_partial():
    s = IngredientPatchSchema(name="Farine complète")
    assert s.name == "Farine complète"


def test_patch_schema_empty_name_raises():
    with pytest.raises(Exception):
        IngredientPatchSchema(name="")


# --- IngredientUpdateSchema ---

def test_update_schema_valid():
    s = IngredientUpdateSchema(name="Sel fin")
    assert s.name == "Sel fin"


def test_update_schema_empty_name_raises():
    with pytest.raises(Exception):
        IngredientUpdateSchema(name="")


# --- IngredientSchema (response) ---

def test_response_schema_from_entity():
    ingredient = Ingredient(
        name="Tomate",
        rayon_uuid=RAYON_UUID,
        main_supplier_uuid=SUPPLIER_UUID,
        secondary_supplier_uuids=[SECONDARY_SUPPLIER_UUID],
        season_months={7: 3},
    )
    schema = IngredientSchema.model_validate(ingredient, from_attributes=True)
    assert schema.name == "Tomate"
    assert str(schema.rayon_uuid) == RAYON_UUID
    assert str(schema.main_supplier_uuid) == SUPPLIER_UUID
    assert [str(uuid) for uuid in schema.secondary_supplier_uuids] == [SECONDARY_SUPPLIER_UUID]
    assert schema.season_months == {7: 3}
