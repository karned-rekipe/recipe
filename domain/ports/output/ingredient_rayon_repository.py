from abc import abstractmethod

from arclith.domain.ports.repository import Repository
from domain.models.ingredient_rayon import IngredientRayon


class IngredientRayonRepository(Repository[IngredientRayon]):
    @abstractmethod
    async def find_by_name(self, name: str) -> list[IngredientRayon]:
        pass

    @abstractmethod
    async def find_page_by_name(
        self,
        name: str,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[IngredientRayon], int]:
        """Return a page of rayons matching a partial name filter and the total count."""
        pass
