from typing import Generic, Protocol, TypeVar, runtime_checkable


@runtime_checkable
class _HasName(Protocol):
    name: str
    is_deleted: bool


T = TypeVar("T", bound=_HasName)


class _FindByNameRepository(Protocol[T]):
    async def find_by_name(self, name: str) -> list[T]: ...


from arclith.domain.ports.logger import Logger


class FindByNameUseCase(Generic[T]):
    def __init__(self, repository: _FindByNameRepository[T], logger: Logger) -> None:
        self._repository = repository
        self._logger = logger

    async def execute(self, name: str) -> list[T]:
        self._logger.info("🔍 Finding entities by name", name=name)
        result = [i for i in await self._repository.find_by_name(name) if not i.is_deleted]
        self._logger.info("✅ Entities found", name=name, count=len(result))
        return result
