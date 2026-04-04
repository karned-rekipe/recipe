from application.use_cases import FindByNameUseCase
from arclith import BaseService, Logger
from domain.models.recipe import Recipe
from domain.ports.output.recipe_repository import RecipeRepository


class RecipeService(BaseService[Recipe]):
    def __init__(self, repository: RecipeRepository, logger: Logger, retention_days: float | None = None) -> None:
        super().__init__(repository, logger, retention_days)
        self._recipe_repo = repository
        self._find_by_name_uc = FindByNameUseCase(repository, logger)

    async def find_by_name(self, name: str) -> list[Recipe]:
        return await self._find_by_name_uc.execute(name)

    async def find_page_filtered(self, name: str | None = None, offset: int = 0, limit: int | None = None) -> tuple[list[Recipe], int]:
        """Return a page of recipes (optionally filtered by name) and total count."""
        if name:
            return await self._recipe_repo.find_page_by_name(name, offset, limit)
        return await self._recipe_repo.find_page(offset, limit)

