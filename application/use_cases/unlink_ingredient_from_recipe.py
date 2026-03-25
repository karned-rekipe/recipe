from arclith.domain.ports.logger import Logger
from uuid6 import UUID

from domain.ports.output.recipe_repository import RecipeRepository


class UnlinkIngredientFromRecipeUseCase:
    def __init__(self, recipe_repo: RecipeRepository, logger: Logger) -> None:
        self._recipe_repo = recipe_repo
        self._logger = logger

    async def execute(self, recipe_uuid: UUID, ingredient_uuid: UUID) -> None:
        self._logger.info("🔗 Unlinking ingredient from recipe", recipe_uuid = str(recipe_uuid),
                          ingredient_uuid = str(ingredient_uuid))
        recipe = await self._recipe_repo.read(recipe_uuid)
        if recipe is None:
            raise ValueError(f"Recipe {recipe_uuid} not found")
        current = list(recipe.ingredients) if recipe.ingredients else []
        updated_list = [i for i in current if i.uuid != ingredient_uuid]
        if len(updated_list) == len(current):
            return
        updated = recipe.model_copy(update = {"ingredients": updated_list or None})
        await self._recipe_repo.update(updated)
        self._logger.info("✅ Ingredient unlinked from recipe", recipe_uuid = str(recipe_uuid),
                          ingredient_uuid = str(ingredient_uuid))
