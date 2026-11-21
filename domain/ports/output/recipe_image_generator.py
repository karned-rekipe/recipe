from abc import ABC, abstractmethod

from domain.models.generated_recipe_image import GeneratedRecipeImage


class RecipeImageGenerator(ABC):
    @abstractmethod
    async def generate(
        self,
        *,
        recipe_uuid: str,
        recipe_name: str,
        ingredients: list[str],
        prompt: str | None = None,
    ) -> GeneratedRecipeImage:
        """Generate and store the main image for a recipe."""
