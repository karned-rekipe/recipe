from typing import Any, Generic, TypeVar

from arclith.domain.ports.logger import Logger

T = TypeVar("T")


class FindByNameUseCase(Generic[T]):
    def __init__(self, repository: Any, logger: Logger) -> None:
        self._repository = repository
        self._logger = logger

    async def execute(self, name: str) -> list[T]:
        self._logger.info("🔍 Finding entities by name", name=name)
        result = [i for i in await self._repository.find_by_name(name) if not i.is_deleted]
        self._logger.info("✅ Entities found", name=name, count=len(result))
        return result
