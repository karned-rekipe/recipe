from arclith.adapters.output.mongodb.config import MongoDBConfig

from adapters.output.mongodb.repositories.recipe_repository import MongoDBRecipeRepository
from domain.models.recipe import Recipe
from domain.models.recipe_equipment import RecipeEquipment
from domain.models.recipe_ingredient import RecipeIngredient
from domain.models.step import Step


def test_to_doc_serializes_nested_aggregate(logger):
    repository = MongoDBRecipeRepository(
        MongoDBConfig(uri="mongodb://localhost:27017", db_name="test"),
        logger,
    )
    recipe = Recipe(
        name="Farine",
        servings=4,
        legacy_id=42,
        migration_metadata={"source_table": "mkg_recipe"},
        main_image="https://example.com/main.jpg",
        secondary_images=["https://example.com/secondary.jpg"],
        ingredients=[RecipeIngredient(name="Farine de ble", quantity=500, unit="g", season_months={})],
        equipment=[RecipeEquipment(name="Saladier", quantity=1)],
        steps=[Step(name="Melanger", rank=1)],
    )

    doc = repository._to_doc(recipe)

    assert doc["_id"] == str(recipe.uuid)
    assert doc["legacy_id"] == 42
    assert doc["migration_metadata"] == {"source_table": "mkg_recipe"}
    assert doc["ingredients"][0]["name"] == "Farine de ble"
    assert doc["equipment"][0]["name"] == "Saladier"
    assert doc["steps"][0]["uuid"] == str(recipe.steps[0].uuid)
    assert doc["created_at"] in {
        recipe.created_at.isoformat(),
        recipe.created_at.isoformat().replace("+00:00", "Z"),
    }


def test_from_doc_restores_nested_aggregate(logger):
    repository = MongoDBRecipeRepository(
        MongoDBConfig(uri="mongodb://localhost:27017", db_name="test"),
        logger,
    )
    original = Recipe(
        name="Farine",
        servings=4,
        legacy_id=42,
        migration_metadata={"source_table": "mkg_recipe"},
        ingredients=[RecipeIngredient(name="Farine de ble", quantity=500, unit="g", season_months={})],
        equipment=[RecipeEquipment(name="Saladier", quantity=1)],
        steps=[Step(name="Melanger", rank=1)],
    )

    restored = repository._from_doc(repository._to_doc(original))

    assert restored.uuid == original.uuid
    assert restored.legacy_id == 42
    assert restored.migration_metadata == {"source_table": "mkg_recipe"}
    assert restored.ingredients[0].name == "Farine de ble"
    assert restored.equipment[0].name == "Saladier"
    assert restored.steps[0].uuid == original.steps[0].uuid
