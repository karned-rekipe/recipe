from abc import abstractmethod
from arclith.domain.ports.repository import Repository

from domain.models.recipe import Recipe


class RecipeRepository(Repository[Recipe]):
    @abstractmethod
    async def find_by_name(self, name: str) -> list[Recipe]:
        pass
