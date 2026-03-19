from arclith import BaseService, Logger
from domain.models.step import Step
from domain.ports.step_repository import StepRepository
from application.use_cases import FindByNameUseCase


class StepService(BaseService[Step]):
    def __init__(self, repository: StepRepository, logger: Logger, retention_days: float | None = None) -> None:
        super().__init__(repository, logger, retention_days)
        self._find_by_name_uc = FindByNameUseCase(repository, logger)

    async def find_by_name(self, name: str) -> list[Step]:
        return await self._find_by_name_uc.execute(name)

