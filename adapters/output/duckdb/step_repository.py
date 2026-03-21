from typing import Any
from uuid import UUID as StdUUID

from arclith.adapters.output.duckdb.repository import DuckDBRepository
from uuid6 import UUID

from domain.models.step import Step
from domain.ports.step_repository import StepRepository


class DuckDBStepRepository(DuckDBRepository[Step], StepRepository):
    def __init__(self, path: str) -> None:
        super().__init__(path, Step)

    def _entity_to_row(self, entity: Step) -> dict[str, Any]:
        row = super()._entity_to_row(entity)
        if isinstance(row.get("recipe_uuid"), (UUID, StdUUID)):
            row["recipe_uuid"] = str(row["recipe_uuid"])
        return row

    def _row_to_entity(self, row: dict[str, Any]) -> Step:
        if isinstance(row.get("recipe_uuid"), str):
            row = {**row, "recipe_uuid": UUID(row["recipe_uuid"])}
        return super()._row_to_entity(row)

    async def find_by_name(self, name: str) -> list[Step]:
        # noinspection SqlNoDataSourceInspection
        rows = self._fetch(
            f"SELECT * FROM {self._table} WHERE deleted_at IS NULL AND lower(name) LIKE ?",
            [f"%{name.lower()}%"],
        )
        return [self._row_to_entity(r) for r in rows]

    async def find_by_recipe(self, recipe_uuid: UUID) -> list[Step]:
        # noinspection SqlNoDataSourceInspection
        rows = self._fetch(
            f"SELECT * FROM {self._table} WHERE deleted_at IS NULL AND recipe_uuid = ?",
            [str(recipe_uuid)],
        )
        return [self._row_to_entity(r) for r in rows]
