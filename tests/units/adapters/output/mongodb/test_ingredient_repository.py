from arclith.adapters.output.mongodb.config import MongoDBConfig

from adapters.output.mongodb.repositories.ingredient_repository import MongoDBIngredientRepository
from domain.models.ingredient import Ingredient

GROUP_UUID = "01951234-5678-7abc-def0-000000000101"
RAYON_UUID = "01951234-5678-7abc-def0-000000000102"
MAIN_SUPPLIER_UUID = "01951234-5678-7abc-def0-000000000103"
SECONDARY_SUPPLIER_UUID = "01951234-5678-7abc-def0-000000000104"


def test_to_doc_serializes_catalog_and_supplier_uuids(logger):
    repository = MongoDBIngredientRepository(
        MongoDBConfig(uri="mongodb://localhost:27017", db_name="test"),
        logger,
    )
    ingredient = Ingredient(
        name="Farine",
        group_uuid=GROUP_UUID,
        rayon_uuid=RAYON_UUID,
        main_supplier_uuid=MAIN_SUPPLIER_UUID,
        secondary_supplier_uuids=[SECONDARY_SUPPLIER_UUID],
    )

    doc = repository._to_doc(ingredient)

    assert doc["_id"] == str(ingredient.uuid)
    assert doc["group_uuid"] == GROUP_UUID
    assert doc["rayon_uuid"] == RAYON_UUID
    assert doc["main_supplier_uuid"] == MAIN_SUPPLIER_UUID
    assert doc["secondary_supplier_uuids"] == [SECONDARY_SUPPLIER_UUID]


def test_from_doc_restores_supplier_uuids(logger):
    repository = MongoDBIngredientRepository(
        MongoDBConfig(uri="mongodb://localhost:27017", db_name="test"),
        logger,
    )
    original = Ingredient(
        name="Farine",
        main_supplier_uuid=MAIN_SUPPLIER_UUID,
        secondary_supplier_uuids=[SECONDARY_SUPPLIER_UUID],
    )

    restored = repository._from_doc(repository._to_doc(original))

    assert restored.uuid == original.uuid
    assert str(restored.main_supplier_uuid) == MAIN_SUPPLIER_UUID
    assert [str(uuid) for uuid in restored.secondary_supplier_uuids] == [SECONDARY_SUPPLIER_UUID]
