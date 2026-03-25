from arclith import BaseService, Logger
from uuid6 import UUID

from application.use_cases import FindByNameUseCase, FindByRecipeUseCase
from domain.models.step import Step
from domain.ports.output.step_repository import StepRepository


class StepService(BaseService[Step]):
    def __init__(self, repository: StepRepository, logger: Logger, retention_days: float | None = None) -> None:
        super().__init__(repository, logger, retention_days)
        self._find_by_name_uc: FindByNameUseCase[Step] = FindByNameUseCase(repository, logger)
        self._find_by_recipe_uc: FindByRecipeUseCase = FindByRecipeUseCase(repository, logger)

    async def find_by_name(self, name: str) -> list[Step]:
        return await self._find_by_name_uc.execute(name)

    async def find_by_recipe(self, recipe_uuid: UUID) -> list[Step]:
        return await self._find_by_recipe_uc.execute(recipe_uuid)

