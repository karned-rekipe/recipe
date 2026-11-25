from abc import ABC, abstractmethod

from domain.models.ingredient_ai_enrichment import IngredientAIEnrichment
from domain.models.ingredient_image_generation import IngredientImageGeneration


class IngredientEnrichmentAgent(ABC):
    @abstractmethod
    async def complete(self, *, ingredient_uuid: str) -> IngredientAIEnrichment:
        """Complete one ingredient and optionally propose its missing image."""

    @abstractmethod
    async def generate_image(self, *, ingredient_uuid: str) -> IngredientImageGeneration:
        """Generate one reviewable ingredient image suggestion."""

    async def generate(self, *, ingredient_uuid: str) -> IngredientImageGeneration:
        """Backward-compatible alias for the former image-only port."""
        return await self.generate_image(ingredient_uuid=ingredient_uuid)
