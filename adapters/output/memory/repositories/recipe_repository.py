from arclith.adapters.output.memory.repository import InMemoryRepository

from domain.models.recipe import Recipe
from domain.ports.output.recipe_repository import RecipeRepository


class InMemoryRecipeRepository(InMemoryRepository[Recipe], RecipeRepository):
    async def find_by_name(self, name: str) -> list[Recipe]:
        return [i for i in self._store.values() if name.lower() in i.name.lower()]
