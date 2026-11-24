from typing import Any

from arclith.adapters.output.mongodb.config import MongoDBConfig
from arclith.adapters.output.mongodb.repository import MongoDBRepository
from arclith.domain.ports.logger import Logger
from domain.models.ingredient_enrichment_suggestion import IngredientEnrichmentSuggestion
from domain.ports.output.ingredient_enrichment_suggestion_repository import IngredientEnrichmentSuggestionRepository
from uuid6 import UUID


class MongoDBIngredientEnrichmentSuggestionRepository(
    MongoDBRepository[IngredientEnrichmentSuggestion],
    IngredientEnrichmentSuggestionRepository,
):
    def __init__(self, config: MongoDBConfig, logger: Logger) -> None:
        super().__init__(config, IngredientEnrichmentSuggestion, logger)

    def _to_doc(self, entity: IngredientEnrichmentSuggestion) -> dict[str, Any]:
        doc = entity.model_dump(mode="json", exclude_computed_fields=True)
        doc["_id"] = doc.pop("uuid")
        return doc

    async def find_by_ingredient_uuid(self, ingredient_uuid: UUID) -> list[IngredientEnrichmentSuggestion]:
        async with self._collection() as col:
            return [
                self._from_doc(doc)
                async for doc in col.find({"ingredient_uuid": str(ingredient_uuid), "deleted_at": None})
            ]

    async def find_pending_by_ingredient_uuid(self, ingredient_uuid: UUID) -> list[IngredientEnrichmentSuggestion]:
        async with self._collection() as col:
            return [
                self._from_doc(doc)
                async for doc in col.find(
                    {"ingredient_uuid": str(ingredient_uuid), "status": "pending", "deleted_at": None}
                )
            ]

    async def find_active_by_ingredient_uuids(
        self,
        ingredient_uuids: list[UUID],
    ) -> list[IngredientEnrichmentSuggestion]:
        if not ingredient_uuids:
            return []
        async with self._collection() as col:
            return [
                self._from_doc(doc)
                async for doc in col.find(
                    {
                        "ingredient_uuid": {"$in": [str(ingredient_uuid) for ingredient_uuid in ingredient_uuids]},
                        "status": {"$in": ["pending", "partially_applied"]},
                        "deleted_at": None,
                    }
                )
            ]
