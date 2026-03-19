from uuid6 import UUID
from arclith.adapters.output.duckdb.repository import DuckDBRepository
from domain.models.step import Step
from domain.ports.step_repository import StepRepository


class DuckDBStepRepository(DuckDBRepository[Step], StepRepository):
    def __init__(self, path: str) -> None:
        super().__init__(path, Step)

    async def find_by_name(self, name: str) -> list[Step]:
        rows = self._fetch(
            f"SELECT * FROM {self._table} WHERE deleted_at IS NULL AND lower(name) LIKE ?",
            [f"%{name.lower()}%"],
        )
        return [self._row_to_entity(r) for r in rows]

    async def find_by_recipe(self, recipe_uuid: UUID) -> list[Step]:
        rows = self._fetch(
            f"SELECT * FROM {self._table} WHERE deleted_at IS NULL AND recipe_uuid = ?",
            [str(recipe_uuid)],
        )
        return [self._row_to_entity(r) for r in rows]

