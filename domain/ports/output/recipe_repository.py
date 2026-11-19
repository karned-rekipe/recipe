from abc import abstractmethod

from arclith.domain.ports.repository import Repository
from domain.models.recipe import Recipe, RecipeStatus
from uuid6 import UUID


class RecipeRepository(Repository[Recipe]):
    @abstractmethod
    async def find_by_name(self, name: str) -> list[Recipe]:
        pass

    @abstractmethod
    async def find_page_by_name(self, name: str, offset: int = 0, limit: int | None = None) -> tuple[list[Recipe], int]:
        """Return a page of recipes matching name filter and the total count."""
        pass

    @abstractmethod
    async def find_page_by_ingredient_uuid(
        self,
        ingredient_uuid: UUID,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Recipe], int]:
        """Return a page of recipes using an ingredient reference and the total count."""
        pass

    @abstractmethod
    async def find_page_by_equipment_uuid(
        self,
        equipment_uuid: UUID,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Recipe], int]:
        """Return a page of recipes using an equipment reference and the total count."""
        pass

    @abstractmethod
    async def find_page_by_tag_uuid(
        self,
        tag_uuid: UUID,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Recipe], int]:
        """Return a page of recipes using a tag reference and the total count."""
        pass

    @abstractmethod
    async def find_by_component_recipe_uuid(self, recipe_uuid: UUID) -> list[Recipe]:
        """Return active recipes that reference the given recipe as a component."""
        pass

    @abstractmethod
    async def find_page_filtered(
        self,
        name: str | None = None,
        ingredient_uuid: UUID | None = None,
        equipment_uuid: UUID | None = None,
        tag_uuid: UUID | None = None,
        difficulty: int | None = None,
        origin_country: str | None = None,
        price: int | None = None,
        favorite: bool | None = None,
        season_month: int | None = None,
        status: RecipeStatus | None = None,
        meal_planner_eligible: bool | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Recipe], int]:
        """Return a page of recipes matching optional filters and the total count."""
        pass

    @abstractmethod
    async def exists_by_ingredient_uuid(self, ingredient_uuid: UUID) -> bool:
        pass

    @abstractmethod
    async def exists_by_equipment_uuid(self, equipment_uuid: UUID) -> bool:
        pass

    @abstractmethod
    async def exists_by_tag_uuid(self, tag_uuid: UUID) -> bool:
        pass
