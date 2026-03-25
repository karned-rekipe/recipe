import re
from arclith.adapters.output.mongodb.config import MongoDBConfig
from arclith.adapters.output.mongodb.repository import MongoDBRepository
from arclith.domain.ports.logger import Logger
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

    @staticmethod
    def _coerce_uuids(items: list[dict], keys: list[str]) -> None:
        for item in items:
            for key in keys:
                if isinstance(item.get(key), str):
                    item[key] = UUID(item[key])

    def _from_doc(self, doc: dict[str, Any]) -> Recipe:
        """Convert MongoDB document to Recipe entity, deserializing nested entities."""
        self._coerce_uuids(doc.get("steps") or [], ["recipe_uuid", "uuid"])
        self._coerce_uuids(doc.get("ingredients") or [], ["uuid"])
        self._coerce_uuids(doc.get("ustensils") or [], ["uuid"])
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

