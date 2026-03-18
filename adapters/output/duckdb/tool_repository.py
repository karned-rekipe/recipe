from arclith.adapters.output.duckdb.repository import DuckDBRepository

from domain.models.tool import Tool
from domain.ports.tool_repository import ToolRepository


class DuckDBToolRepository(DuckDBRepository[Tool], ToolRepository):
    def __init__(self, path: str) -> None:
        super().__init__(path, Tool)

    async def find_by_name(self, name: str) -> list[Tool]:
        rows = self._fetch(
            f"SELECT * FROM {self._table} WHERE deleted_at IS NULL AND lower(name) LIKE ?",
            [f"%{name.lower()}%"],
        )
        return [self._row_to_entity(r) for r in rows]

