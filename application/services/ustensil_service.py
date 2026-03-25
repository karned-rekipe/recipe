from arclith import BaseService, Logger

from application.use_cases import FindByNameUseCase
from domain.models.ustensil import Ustensil
from domain.ports.output.ustensil_repository import UstensilRepository


class UstensilService(BaseService[Ustensil]):
    def __init__(self, repository: UstensilRepository, logger: Logger, retention_days: float | None = None) -> None:
        super().__init__(repository, logger, retention_days)
        self._find_by_name_uc: FindByNameUseCase[Ustensil] = FindByNameUseCase(repository, logger)

    async def find_by_name(self, name: str) -> list[Ustensil]:
        return await self._find_by_name_uc.execute(name)
