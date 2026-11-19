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
