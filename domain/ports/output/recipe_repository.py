from abc import abstractmethod

from arclith.domain.ports.repository import Repository
from domain.models.recipe import Recipe


class RecipeRepository(Repository[Recipe]):
    @abstractmethod
    async def find_by_name(self, name: str) -> list[Recipe]:
        pass

    @abstractmethod
    async def find_page_by_name(self, name: str, offset: int = 0, limit: int | None = None) -> tuple[list[Recipe], int]:
        """Return a page of recipes matching name filter and the total count."""
        pass

