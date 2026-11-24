from abc import ABC, abstractmethod

from domain.models.ingredient_image_generation import IngredientImageGeneration


class IngredientImageGenerationAgent(ABC):
    @abstractmethod
    async def generate(self, *, ingredient_uuid: str) -> IngredientImageGeneration:
        """Generate one reviewable ingredient image suggestion through the internal agent."""
