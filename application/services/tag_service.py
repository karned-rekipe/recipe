from arclith import BaseService, Logger
from domain.models.tag import Tag
from domain.ports.output.tag_repository import TagRepository


class TagService(BaseService[Tag]):
    def __init__(self, repository: TagRepository, logger: Logger, retention_days: float | None = None) -> None:
        super().__init__(repository, logger, retention_days)
        self._tag_repo = repository

    @property
    def repository(self) -> TagRepository:
        return self._tag_repo

    async def find_by_name(self, name: str) -> list[Tag]:
        self._logger.info("🔍 Finding tags by name", name=name)
        result = [item for item in await self._tag_repo.find_by_name(name) if not item.is_deleted]
        self._logger.info("✅ Tags found", name=name, count=len(result))
        return result

    async def find_page_filtered(self, name: str | None = None, offset: int = 0, limit: int | None = None) -> tuple[list[Tag], int]:
        if name:
            return await self._tag_repo.find_page_by_name(name, offset, limit)
        return await self._tag_repo.find_page(offset, limit)
