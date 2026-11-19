from abc import abstractmethod

from arclith.domain.ports.repository import Repository
from domain.models.ingredient_enrichment_suggestion import IngredientEnrichmentSuggestion
from uuid6 import UUID


class IngredientEnrichmentSuggestionRepository(Repository[IngredientEnrichmentSuggestion]):
    @abstractmethod
    async def find_by_ingredient_uuid(self, ingredient_uuid: UUID) -> list[IngredientEnrichmentSuggestion]:
        pass

    @abstractmethod
    async def find_pending_by_ingredient_uuid(self, ingredient_uuid: UUID) -> list[IngredientEnrichmentSuggestion]:
        pass
