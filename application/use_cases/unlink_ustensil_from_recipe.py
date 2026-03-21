from arclith.domain.ports.logger import Logger
from uuid6 import UUID

from domain.ports.recipe_repository import RecipeRepository


class UnlinkUstensilFromRecipeUseCase:
    def __init__(self, recipe_repo: RecipeRepository, logger: Logger) -> None:
        self._recipe_repo = recipe_repo
        self._logger = logger

    async def execute(self, recipe_uuid: UUID, ustensil_uuid: UUID) -> None:
        self._logger.info("🔗 Unlinking ustensil from recipe", recipe_uuid = str(recipe_uuid),
                          ustensil_uuid = str(ustensil_uuid))
        recipe = await self._recipe_repo.read(recipe_uuid)
        if recipe is None:
            raise ValueError(f"Recipe {recipe_uuid} not found")
        current = list(recipe.ustensils) if recipe.ustensils else []
        updated_list = [u for u in current if u.uuid != ustensil_uuid]
        if len(updated_list) == len(current):
            return
        updated = recipe.model_copy(update = {"ustensils": updated_list or None})
        await self._recipe_repo.update(updated)
        self._logger.info("✅ Ustensil unlinked from recipe", recipe_uuid = str(recipe_uuid),
                          ustensil_uuid = str(ustensil_uuid))
