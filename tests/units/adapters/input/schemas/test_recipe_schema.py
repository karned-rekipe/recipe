import pytest
from datetime import datetime, timezone

from adapters.input.schemas.recipe_schema import (
    RecipeCreateSchema,
    RecipePatchSchema,
    RecipeSchema,
    RecipeUpdateSchema,
)
from domain.models.recipe import Recipe


# --- RecipeCreateSchema ---

def test_create_schema_valid():
    s = RecipeCreateSchema(name="Farine")
    assert s.name == "Farine"


def test_create_schema_empty_name_raises():
    with pytest.raises(Exception):
        RecipeCreateSchema(name="")


# --- RecipePatchSchema ---

def test_patch_schema_all_none():
    s = RecipePatchSchema()
    assert s.name is None


def test_patch_schema_partial():
    s = RecipePatchSchema(name="Farine complète")
    assert s.name == "Farine complète"


def test_patch_schema_empty_name_raises():
    with pytest.raises(Exception):
        RecipePatchSchema(name="")


# --- RecipeUpdateSchema ---

def test_update_schema_valid():
    s = RecipeUpdateSchema(name="Sel fin")
    assert s.name == "Sel fin"


def test_update_schema_empty_name_raises():
    with pytest.raises(Exception):
        RecipeUpdateSchema(name="")


# --- RecipeSchema (response) ---

def test_recipe_schema_from_entity():
    entity = Recipe(name="Farine")
    schema = RecipeSchema.model_validate(entity)
    assert schema.name == "Farine"
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

