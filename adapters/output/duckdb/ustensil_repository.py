from arclith.adapters.output.duckdb.repository import DuckDBRepository

from domain.models.ustensil import Ustensil
from domain.ports.ustensil_repository import UstensilRepository


class DuckDBUstensilRepository(DuckDBRepository[Ustensil], UstensilRepository):
    def __init__(self, path: str) -> None:
        super().__init__(path, Ustensil)

    async def find_by_name(self, name: str) -> list[Ustensil]:
        rows = self._fetch(
            f"SELECT * FROM {self._table} WHERE deleted_at IS NULL AND lower(name) LIKE ?",
            [f"%{name.lower()}%"],
        )
        return [self._row_to_entity(r) for r in rows]
