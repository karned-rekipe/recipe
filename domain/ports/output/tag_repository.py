from abc import abstractmethod

from arclith.domain.ports.repository import Repository
from domain.models.tag import Tag


class TagRepository(Repository[Tag]):
    @abstractmethod
    async def find_by_name(self, name: str) -> list[Tag]:
        pass

    @abstractmethod
    async def find_page_by_name(self, name: str, offset: int = 0, limit: int | None = None) -> tuple[list[Tag], int]:
        """Return a page of tags matching a partial name filter and the total count."""
        pass
