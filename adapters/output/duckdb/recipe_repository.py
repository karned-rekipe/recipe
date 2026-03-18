from arclith.adapters.output.duckdb.repository import DuckDBRepository
from domain.models.recipe import Recipe
from domain.ports.recipe_repository import RecipeRepository


class DuckDBRecipeRepository(DuckDBRepository[Recipe], RecipeRepository):
    def __init__(self, path: str) -> None:
        super().__init__(path, Recipe)

    async def find_by_name(self, name: str) -> list[Recipe]:
        rows = self._fetch(
            f"SELECT * FROM {self._table} WHERE deleted_at IS NULL AND lower(name) LIKE ?",
            [f"%{name.lower()}%"],
        )
        return [self._row_to_entity(r) for r in rows]

