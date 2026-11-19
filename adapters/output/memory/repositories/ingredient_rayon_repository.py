from arclith.adapters.output.memory.repository import InMemoryRepository
from domain.models.ingredient_rayon import IngredientRayon
from domain.ports.output.ingredient_rayon_repository import IngredientRayonRepository


class InMemoryIngredientRayonRepository(InMemoryRepository[IngredientRayon], IngredientRayonRepository):
    async def find_by_name(self, name: str) -> list[IngredientRayon]:
        return [item for item in self._store.values() if name.lower() in item.name.lower() and not item.is_deleted]

    async def find_page_by_name(
        self,
        name: str,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[IngredientRayon], int]:
        filtered = [item for item in self._store.values() if name.lower() in item.name.lower() and not item.is_deleted]
        total = len(filtered)
        page = filtered[offset: offset + limit] if limit is not None else filtered[offset:]
        return page, total
