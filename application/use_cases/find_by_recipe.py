from uuid6 import UUID

from arclith.domain.ports.logger import Logger

from domain.models.step import Step
from domain.ports.step_repository import StepRepository


class FindByRecipeUseCase:
    def __init__(self, repository: StepRepository, logger: Logger) -> None:
        self._repository = repository
        self._logger = logger

    async def execute(self, recipe_uuid: UUID) -> list[Step]:
        self._logger.info("🔍 Finding steps by recipe", recipe_uuid=str(recipe_uuid))
        result = await self._repository.find_by_recipe(recipe_uuid)
        self._logger.info("✅ Steps found", recipe_uuid=str(recipe_uuid), count=len(result))
        return result

