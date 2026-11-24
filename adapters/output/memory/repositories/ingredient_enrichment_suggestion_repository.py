from arclith.adapters.output.memory.repository import InMemoryRepository
from domain.models.ingredient_enrichment_suggestion import IngredientEnrichmentSuggestion
from domain.ports.output.ingredient_enrichment_suggestion_repository import IngredientEnrichmentSuggestionRepository
from uuid6 import UUID


class InMemoryIngredientEnrichmentSuggestionRepository(
    InMemoryRepository[IngredientEnrichmentSuggestion],
    IngredientEnrichmentSuggestionRepository,
):
    async def find_by_ingredient_uuid(self, ingredient_uuid: UUID) -> list[IngredientEnrichmentSuggestion]:
        return [
            suggestion
            for suggestion in self._store.values()
            if str(suggestion.ingredient_uuid) == str(ingredient_uuid) and not suggestion.is_deleted
        ]

    async def find_pending_by_ingredient_uuid(self, ingredient_uuid: UUID) -> list[IngredientEnrichmentSuggestion]:
        return [
            suggestion
            for suggestion in await self.find_by_ingredient_uuid(ingredient_uuid)
            if suggestion.status == "pending"
        ]

    async def find_active_by_ingredient_uuids(
        self,
        ingredient_uuids: list[UUID],
    ) -> list[IngredientEnrichmentSuggestion]:
        target_uuids = {str(ingredient_uuid) for ingredient_uuid in ingredient_uuids}
        return [
            suggestion
            for suggestion in self._store.values()
            if str(suggestion.ingredient_uuid) in target_uuids
            and suggestion.status in {"pending", "partially_applied"}
            and not suggestion.is_deleted
        ]
