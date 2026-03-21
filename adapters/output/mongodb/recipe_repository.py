from arclith.adapters.output.mongodb.config import MongoDBConfig
from arclith.adapters.output.mongodb.repository import MongoDBRepository
from arclith.domain.ports.logger import Logger
import re
from typing import Any
from uuid6 import UUID

from domain.models.recipe import Recipe
from domain.ports.recipe_repository import RecipeRepository


class MongoDBRecipeRepository(MongoDBRepository[Recipe], RecipeRepository):
    def __init__(self, config: MongoDBConfig, logger: Logger) -> None:
        super().__init__(config, Recipe, logger)

    def _to_doc(self, entity: Recipe) -> dict[str, Any]:
        """Convert Recipe entity to MongoDB document, serializing nested entities."""
        doc = super()._to_doc(entity)

        # Serialize nested entities to dicts with mode='json' to properly handle UUIDs
        if entity.ingredients:
            doc["ingredients"] = [ing.model_dump(mode='json') for ing in entity.ingredients]

        if entity.ustensils:
            doc["ustensils"] = [ust.model_dump(mode='json') for ust in entity.ustensils]

        if entity.steps:
            doc["steps"] = [step.model_dump(mode='json') for step in entity.steps]

        return doc

    def _from_doc(self, doc: dict[str, Any]) -> Recipe:
        """Convert MongoDB document to Recipe entity, deserializing nested entities."""
        # Convert string UUIDs back to UUID objects for nested entities
        if "steps" in doc and doc["steps"]:
            for step in doc["steps"]:
                if "recipe_uuid" in step and isinstance(step["recipe_uuid"], str):
                    step["recipe_uuid"] = UUID(step["recipe_uuid"])
                if "uuid" in step and isinstance(step["uuid"], str):
                    step["uuid"] = UUID(step["uuid"])

        if "ingredients" in doc and doc["ingredients"]:
            for ing in doc["ingredients"]:
                if "uuid" in ing and isinstance(ing["uuid"], str):
                    ing["uuid"] = UUID(ing["uuid"])

        if "ustensils" in doc and doc["ustensils"]:
            for ust in doc["ustensils"]:
                if "uuid" in ust and isinstance(ust["uuid"], str):
                    ust["uuid"] = UUID(ust["uuid"])

        # Let the parent handle the base conversion
        return super()._from_doc(doc)

    async def find_by_name(self, name: str) -> list[Recipe]:
        async with self._collection() as col:
            escaped_name = re.escape(name)
            return [
                self._from_doc(doc)
                async for doc in col.find(
                    {"name": {"$regex": escaped_name, "$options": "i"}, "deleted_at": None}
                )
            ]

