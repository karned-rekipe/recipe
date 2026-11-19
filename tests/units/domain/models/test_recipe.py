import pytest
from domain.models.recipe import Recipe, RecipeQualityStatus, RecipeStatus


def test_valid_recipe():
    i = Recipe(name="Farine")
    assert i.name == "Farine"


def test_name_stripped():
    i = Recipe(name="  Sel fin  ")
    assert i.name == "Sel fin"


def test_empty_name_raises():
    with pytest.raises(Exception):
        Recipe(name="")


def test_blank_name_raises():
    with pytest.raises(Exception):
        Recipe(name="   ")



def test_inherits_entity_fields():
    from uuid6 import UUID
    i = Recipe(name="Sel")
    assert isinstance(i.uuid, UUID)
    assert i.version == 1
    assert not i.is_deleted


def test_model_copy_update():
    i = Recipe(name="Farine")
    copy = i.model_copy(update={"name": "Farine complète"})
    assert copy.name == "Farine complète"
    assert copy.uuid == i.uuid


def test_defaults_are_migration_ready():
    recipe = Recipe(name="Farine")
    assert recipe.favorite is False
    assert recipe.status == RecipeStatus.active
    assert recipe.quality_status == RecipeQualityStatus.structured
    assert recipe.legacy_id is None
    assert recipe.migration_metadata == {}


def test_accepts_legacy_migration_metadata():
    recipe = Recipe(
        name="Farine",
        legacy_id=42,
        status=RecipeStatus.archived,
        quality_status=RecipeQualityStatus.text_only,
        migration_metadata={"source_table": "mkg_recipe", "imported": True},
    )
    assert recipe.legacy_id == 42
    assert recipe.status == RecipeStatus.archived
    assert recipe.quality_status == RecipeQualityStatus.text_only
    assert recipe.migration_metadata["source_table"] == "mkg_recipe"
