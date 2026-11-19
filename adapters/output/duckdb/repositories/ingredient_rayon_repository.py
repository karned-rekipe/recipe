from arclith.adapters.output.duckdb.repository import DuckDBRepository
from domain.models.ingredient_rayon import IngredientRayon
from domain.ports.output.ingredient_rayon_repository import IngredientRayonRepository


class DuckDBIngredientRayonRepository(DuckDBRepository[IngredientRayon], IngredientRayonRepository):
    def __init__(self, path: str) -> None:
        super().__init__(path, IngredientRayon)

    async def find_by_name(self, name: str) -> list[IngredientRayon]:
        rows = self._fetch(
            f"SELECT * FROM {self._table} WHERE deleted_at IS NULL AND lower(name) LIKE ?",  # nosec B608
            [f"%{name.lower()}%"],
        )
        return [self._row_to_entity(row) for row in rows]

    async def find_page_by_name(
        self,
        name: str,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[IngredientRayon], int]:
        items = await self.find_by_name(name)
        total = len(items)
        page = items[offset: offset + limit] if limit is not None else items[offset:]
        return page, total
