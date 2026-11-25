from pydantic import model_validator

from domain.models.ingredient_ai_enrichment import IngredientAIEnrichment


class IngredientImageGeneration(IngredientAIEnrichment):
    """Validated outcome returned by the internal ingredient agent."""

    @model_validator(mode="after")
    def image_only_suggestion(self) -> "IngredientImageGeneration":
        if not self.suggestion_uuid:
            raise ValueError("Ingredient image generation must create a suggestion")
        if self.proposed_fields != ["media_profile"]:
            raise ValueError("Ingredient image generation must only propose media_profile")
        return self
