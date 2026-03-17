from arclith import BaseService, Logger
from domain.models.recipe import Recipe
from domain.ports.recipe_repository import RecipeRepository
from application.use_cases import FindByNameUseCase


class RecipeService(BaseService[Recipe]):
    def __init__(self, repository: RecipeRepository, logger: Logger, retention_days: float | None = None) -> None:
        super().__init__(repository, logger, retention_days)
        self._find_by_name_uc = FindByNameUseCase(repository, logger)

    async def find_by_name(self, name: str) -> list[Recipe]:
        return await self._find_by_name_uc.execute(name)

