from arclith import BaseService, Logger
from domain.models.tool import Tool
from domain.ports.tool_repository import ToolRepository
from application.use_cases import FindByNameUseCase


class ToolService(BaseService[Tool]):
    def __init__(self, repository: ToolRepository, logger: Logger, retention_days: float | None = None) -> None:
        super().__init__(repository, logger, retention_days)
        self._find_by_name_uc = FindByNameUseCase(repository, logger)

    async def find_by_name(self, name: str) -> list[Tool]:
        return await self._find_by_name_uc.execute(name)

