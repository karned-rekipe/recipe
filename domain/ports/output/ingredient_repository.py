from abc import abstractmethod

from arclith.domain.ports.repository import Repository
from domain.models.ingredient import Ingredient
from uuid6 import UUID


class IngredientRepository(Repository[Ingredient]):
    @abstractmethod
    async def find_by_name(self, name: str) -> list[Ingredient]:
        pass

    @abstractmethod
    async def find_page_by_name(self, name: str, offset: int = 0, limit: int | None = None) -> tuple[list[Ingredient], int]:
        """Return a page of ingredients matching name filter and the total count."""
        pass

    @abstractmethod
    async def find_page_filtered(
        self,
        name: str | None = None,
        group_uuid: UUID | None = None,
        rayon_uuid: UUID | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Ingredient], int]:
        """Return a page of ingredients matching optional filters and the total count."""
        pass

    @abstractmethod
    async def exists_by_group_uuid(self, group_uuid: UUID) -> bool:
        pass

    @abstractmethod
    async def exists_by_rayon_uuid(self, rayon_uuid: UUID) -> bool:
        pass
