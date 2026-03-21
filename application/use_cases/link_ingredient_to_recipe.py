from arclith.domain.ports.logger import Logger
from uuid6 import UUID

from domain.models.recipe import Recipe
from domain.ports.ingredient_repository import IngredientRepository
from domain.ports.recipe_repository import RecipeRepository


class LinkIngredientToRecipeUseCase:
    def __init__(self, recipe_repo: RecipeRepository, ingredient_repo: IngredientRepository, logger: Logger) -> None:
        self._recipe_repo = recipe_repo
        self._ingredient_repo = ingredient_repo
        self._logger = logger

    async def execute(self, recipe_uuid: UUID, ingredient_uuid: UUID) -> Recipe:
        self._logger.info("🔗 Linking ingredient to recipe", recipe_uuid = str(recipe_uuid),
                          ingredient_uuid = str(ingredient_uuid))
        recipe = await self._recipe_repo.read(recipe_uuid)
        if recipe is None:
            raise ValueError(f"Recipe {recipe_uuid} not found")
        ingredient = await self._ingredient_repo.read(ingredient_uuid)
        if ingredient is None:
            raise ValueError(f"Ingredient {ingredient_uuid} not found")
        current = list(recipe.ingredients) if recipe.ingredients else []
        if any(i.uuid == ingredient_uuid for i in current):
            self._logger.info("ℹ️ Ingredient already linked", recipe_uuid = str(recipe_uuid),
                              ingredient_uuid = str(ingredient_uuid))
            return recipe
        updated = recipe.model_copy(update = {"ingredients": [*current, ingredient]})
        await self._recipe_repo.update(updated)
        self._logger.info("✅ Ingredient linked to recipe", recipe_uuid = str(recipe_uuid),
                          ingredient_uuid = str(ingredient_uuid))
        return updated
