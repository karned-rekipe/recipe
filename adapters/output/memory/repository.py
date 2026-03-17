from arclith.adapters.output.memory.repository import InMemoryRepository
from domain.models.ingredient import Ingredient
from domain.models.recipe import Recipe
from domain.models.tool import Tool
from domain.ports.ingredient_repository import IngredientRepository
from domain.ports.recipe_repository import RecipeRepository
from domain.ports.tool_repository import ToolRepository


class InMemoryIngredientRepository(InMemoryRepository[Ingredient], IngredientRepository):
    async def find_by_name(self, name: str) -> list[Ingredient]:
        return [i for i in self._store.values() if name.lower() in i.name.lower()]

class InMemoryToolRepository(InMemoryRepository[Tool], ToolRepository):
    async def find_by_name(self, name: str) -> list[Tool]:
        return [i for i in self._store.values() if name.lower() in i.name.lower()]

class InMemoryRecipeRepository(InMemoryRepository[Recipe], RecipeRepository):
    async def find_by_name(self, name: str) -> list[Recipe]:
        return [i for i in self._store.values() if name.lower() in i.name.lower()]

