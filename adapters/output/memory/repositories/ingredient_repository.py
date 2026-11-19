from arclith.adapters.output.memory.repository import InMemoryRepository
from domain.models.ingredient import Ingredient
from domain.ports.output.ingredient_repository import IngredientRepository
from uuid6 import UUID


class InMemoryIngredientRepository(InMemoryRepository[Ingredient], IngredientRepository):
    async def find_by_name(self, name: str) -> list[Ingredient]:
        return [i for i in self._store.values() if name.lower() in i.name.lower() and not i.is_deleted]

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
        filtered = [
            item
            for item in self._store.values()
            if not item.is_deleted
            and (not name or name.lower() in item.name.lower())
            and (group_uuid is None or str(item.group_uuid) == str(group_uuid))
            and (rayon_uuid is None or str(item.rayon_uuid) == str(rayon_uuid))
        ]
        total = len(filtered)
        page = filtered[offset: offset + limit] if limit is not None else filtered[offset:]
        return page, total

    async def exists_by_group_uuid(self, group_uuid: UUID) -> bool:
        return any(not item.is_deleted and str(item.group_uuid) == str(group_uuid) for item in self._store.values())

    async def exists_by_rayon_uuid(self, rayon_uuid: UUID) -> bool:
        return any(not item.is_deleted and str(item.rayon_uuid) == str(rayon_uuid) for item in self._store.values())
