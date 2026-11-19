from arclith.adapters.output.duckdb.repository import DuckDBRepository
from domain.models.ingredient import Ingredient
from domain.ports.output.ingredient_repository import IngredientRepository
from uuid6 import UUID


class DuckDBIngredientRepository(DuckDBRepository[Ingredient], IngredientRepository):
    def __init__(self, path: str) -> None:
        super().__init__(path, Ingredient)

    # noinspection SqlNoDataSourceInspection
    async def find_by_name(self, name: str) -> list[Ingredient]:
        rows = self._fetch(
            f"SELECT * FROM {self._table} WHERE deleted_at IS NULL AND lower(name) LIKE ?",  # nosec B608
            [f"%{name.lower()}%"],
        )
        return [self._row_to_entity(r) for r in rows]

    # noinspection SqlNoDataSourceInspection
    async def find_page_by_name(self, name: str, offset: int = 0, limit: int | None = None) -> tuple[list[Ingredient], int]:
        return await self.find_page_filtered(name=name, offset=offset, limit=limit)

    async def find_page_filtered(
        self,
        name: str | None = None,
        group_uuid: UUID | None = None,
        rayon_uuid: UUID | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Ingredient], int]:
        items = await self.find_all()
        filtered = [
            item
            for item in items
            if (not name or name.lower() in item.name.lower())
            and (group_uuid is None or str(item.group_uuid) == str(group_uuid))
            and (rayon_uuid is None or str(item.rayon_uuid) == str(rayon_uuid))
        ]
        total = len(filtered)
        page = filtered[offset: offset + limit] if limit is not None else filtered[offset:]
        return page, total

    async def exists_by_group_uuid(self, group_uuid: UUID) -> bool:
        items = await self.find_page_filtered(group_uuid=group_uuid, offset=0, limit=1)
        return bool(items[0])

    async def exists_by_rayon_uuid(self, rayon_uuid: UUID) -> bool:
        items = await self.find_page_filtered(rayon_uuid=rayon_uuid, offset=0, limit=1)
        return bool(items[0])
