from arclith import BaseService, Logger
from uuid6 import UUID

from application.use_cases import (
    FindByNameUseCase,
    LinkIngredientToRecipeUseCase,
    LinkUstensilToRecipeUseCase,
    UnlinkIngredientFromRecipeUseCase,
    UnlinkUstensilFromRecipeUseCase,
)
from domain.models.recipe import Recipe
from domain.ports.output.ingredient_repository import IngredientRepository
from domain.ports.output.recipe_repository import RecipeRepository
from domain.ports.output.ustensil_repository import UstensilRepository


class RecipeService(BaseService[Recipe]):
    def __init__(
            self,
            repository: RecipeRepository,
            ingredient_repo: IngredientRepository,
            ustensil_repo: UstensilRepository,
            logger: Logger,
            retention_days: float | None = None,
    ) -> None:
        super().__init__(repository, logger, retention_days)
        self._find_by_name_uc: FindByNameUseCase[Recipe] = FindByNameUseCase(repository, logger)
        self._link_ingredient_uc: LinkIngredientToRecipeUseCase = LinkIngredientToRecipeUseCase(repository,
                                                                                                ingredient_repo, logger)
        self._unlink_ingredient_uc: UnlinkIngredientFromRecipeUseCase = UnlinkIngredientFromRecipeUseCase(repository,
                                                                                                          logger)
        self._link_ustensil_uc: LinkUstensilToRecipeUseCase = LinkUstensilToRecipeUseCase(repository, ustensil_repo,
                                                                                          logger)
        self._unlink_ustensil_uc: UnlinkUstensilFromRecipeUseCase = UnlinkUstensilFromRecipeUseCase(repository, logger)

    async def find_by_name(self, name: str) -> list[Recipe]:
        return await self._find_by_name_uc.execute(name)

    async def add_ingredient(self, recipe_uuid: UUID, ingredient_uuid: UUID) -> Recipe:
        return await self._link_ingredient_uc.execute(recipe_uuid, ingredient_uuid)

    async def remove_ingredient(self, recipe_uuid: UUID, ingredient_uuid: UUID) -> None:
        await self._unlink_ingredient_uc.execute(recipe_uuid, ingredient_uuid)

    async def add_ustensil(self, recipe_uuid: UUID, ustensil_uuid: UUID) -> Recipe:
        return await self._link_ustensil_uc.execute(recipe_uuid, ustensil_uuid)

    async def remove_ustensil(self, recipe_uuid: UUID, ustensil_uuid: UUID) -> None:
        await self._unlink_ustensil_uc.execute(recipe_uuid, ustensil_uuid)
