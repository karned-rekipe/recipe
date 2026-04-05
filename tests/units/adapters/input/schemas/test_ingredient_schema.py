import pytest

from adapters.input.schemas.ingredient_schema import (
    IngredientCreateSchema,
    IngredientPatchSchema,
    IngredientSchema,
    IngredientUpdateSchema,
)
from domain.models.ingredient import Ingredient


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
        rayon="fruits et légumes",
        group="légumes",
        green_score=80,
        unit="g",
        quantity=100.0,
        season_months={7: 3},
    )
    assert s.rayon == "fruits et légumes"
    assert s.group == "légumes"
    assert s.green_score == 80
    assert s.unit == "g"
    assert s.quantity == 100.0


# --- IngredientPatchSchema ---

def test_patch_schema_all_none():
    s = IngredientPatchSchema()
    assert s.name is None
    assert s.rayon is None
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
    ingredient = Ingredient(name="Tomate", rayon="fruits et légumes", season_months={7: 3})
    schema = IngredientSchema.model_validate(ingredient, from_attributes=True)
    assert schema.name == "Tomate"
    assert schema.rayon == "fruits et légumes"
    assert schema.season_months == {7: 3}
