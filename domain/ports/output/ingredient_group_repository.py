from abc import abstractmethod

from arclith.domain.ports.repository import Repository
from domain.models.ingredient_group import IngredientGroup


class IngredientGroupRepository(Repository[IngredientGroup]):
    @abstractmethod
    async def find_by_name(self, name: str) -> list[IngredientGroup]:
        pass

    @abstractmethod
    async def find_page_by_name(
        self,
        name: str,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[IngredientGroup], int]:
        """Return a page of groups matching a partial name filter and the total count."""
        pass
