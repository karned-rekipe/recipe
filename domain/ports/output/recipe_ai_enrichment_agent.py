from abc import ABC, abstractmethod

from domain.models.recipe_ai_enrichment import RecipeAIEnrichment


class RecipeAIEnrichmentAgent(ABC):
    @abstractmethod
    async def enrich(
        self,
        *,
        recipe_uuid: str,
        generate_image: bool = True,
    ) -> RecipeAIEnrichment:
        """Enrich an existing recipe through the internal AI agent MCP."""
