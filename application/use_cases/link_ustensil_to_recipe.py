from arclith.domain.ports.logger import Logger
from uuid6 import UUID

from domain.models.recipe import Recipe
from domain.ports.recipe_repository import RecipeRepository
from domain.ports.ustensil_repository import UstensilRepository


class LinkUstensilToRecipeUseCase:
    def __init__(self, recipe_repo: RecipeRepository, ustensil_repo: UstensilRepository, logger: Logger) -> None:
        self._recipe_repo = recipe_repo
        self._ustensil_repo = ustensil_repo
        self._logger = logger

    async def execute(self, recipe_uuid: UUID, ustensil_uuid: UUID) -> Recipe:
        self._logger.info("🔗 Linking ustensil to recipe", recipe_uuid = str(recipe_uuid),
                          ustensil_uuid = str(ustensil_uuid))
        recipe = await self._recipe_repo.read(recipe_uuid)
        if recipe is None:
            raise ValueError(f"Recipe {recipe_uuid} not found")
        ustensil = await self._ustensil_repo.read(ustensil_uuid)
        if ustensil is None:
            raise ValueError(f"Ustensil {ustensil_uuid} not found")
        current = list(recipe.ustensils) if recipe.ustensils else []
        if any(u.uuid == ustensil_uuid for u in current):
            self._logger.info("ℹ️ Ustensil already linked", recipe_uuid = str(recipe_uuid),
                              ustensil_uuid = str(ustensil_uuid))
            return recipe
        updated = recipe.model_copy(update = {"ustensils": [*current, ustensil]})
        await self._recipe_repo.update(updated)
        self._logger.info("✅ Ustensil linked to recipe", recipe_uuid = str(recipe_uuid),
                          ustensil_uuid = str(ustensil_uuid))
        return updated
