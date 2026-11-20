from arclith.adapters.output.mongodb.config import MongoDBConfig

from adapters.output.mongodb.repositories.recipe_repository import MongoDBRecipeRepository
from domain.models.recipe import Recipe
from domain.models.recipe_component import RecipeComponent
from domain.models.recipe_equipment import RecipeEquipment
from domain.models.recipe_ingredient import RecipeIngredient
from domain.models.step import Step

INGREDIENT_UUID = "01951234-5678-7abc-def0-000000000101"
EQUIPMENT_UUID = "01951234-5678-7abc-def0-000000000102"
COMPONENT_RECIPE_UUID = "01951234-5678-7abc-def0-000000000201"


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
        components=[RecipeComponent(recipe_uuid=COMPONENT_RECIPE_UUID, label="Crème anglaise", rank=1)],
        ingredients=[RecipeIngredient(ingredient_uuid=INGREDIENT_UUID, quantity=500, unit="g")],
        equipment=[RecipeEquipment(equipment_uuid=EQUIPMENT_UUID, quantity=1)],
        steps=[Step(name="Melanger", rank=1)],
    )

    doc = repository._to_doc(recipe)

    assert doc["_id"] == str(recipe.uuid)
    assert doc["legacy_id"] == 42
    assert doc["migration_metadata"] == {"source_table": "mkg_recipe"}
    assert doc["components"][0]["recipe_uuid"] == COMPONENT_RECIPE_UUID
    assert doc["ingredients"][0]["ingredient_uuid"] == INGREDIENT_UUID
    assert doc["equipment"][0]["equipment_uuid"] == EQUIPMENT_UUID
    assert doc["steps"][0]["uuid"] == str(recipe.steps[0].uuid)
    assert doc["created_at"] in {
        recipe.created_at.isoformat(),
        recipe.created_at.isoformat().replace("+00:00", "Z"),
    }


def test_to_doc_omits_empty_legacy_id(logger):
    repository = MongoDBRecipeRepository(
        MongoDBConfig(uri="mongodb://localhost:27017", db_name="test"),
        logger,
    )
    recipe = Recipe(name="Recette IA")

    doc = repository._to_doc(recipe)

    assert "legacy_id" not in doc


def test_from_doc_restores_nested_aggregate(logger):
    repository = MongoDBRecipeRepository(
        MongoDBConfig(uri="mongodb://localhost:27017", db_name="test"),
        logger,
    )
    component = RecipeComponent(recipe_uuid=COMPONENT_RECIPE_UUID, label="Crème anglaise", rank=1)
    original = Recipe(
        name="Farine",
        servings=4,
        legacy_id=42,
        migration_metadata={"source_table": "mkg_recipe"},
        components=[component],
        ingredients=[RecipeIngredient(ingredient_uuid=INGREDIENT_UUID, quantity=500, unit="g")],
        equipment=[RecipeEquipment(equipment_uuid=EQUIPMENT_UUID, quantity=1)],
        steps=[
            Step(
                name="Melanger",
                rank=1,
                component_uuid=component.uuid,
                source_recipe_uuid=component.recipe_uuid,
            )
        ],
    )

    restored = repository._from_doc(repository._to_doc(original))

    assert restored.uuid == original.uuid
    assert restored.legacy_id == 42
    assert restored.migration_metadata == {"source_table": "mkg_recipe"}
    assert str(restored.components[0].recipe_uuid) == COMPONENT_RECIPE_UUID
    assert restored.components[0].label == "Crème anglaise"
    assert str(restored.ingredients[0].ingredient_uuid) == INGREDIENT_UUID
    assert str(restored.equipment[0].equipment_uuid) == EQUIPMENT_UUID
    assert restored.steps[0].uuid == original.steps[0].uuid
    assert restored.steps[0].component_uuid == component.uuid
    assert restored.steps[0].source_recipe_uuid == component.recipe_uuid
