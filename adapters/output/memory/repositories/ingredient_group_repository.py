from arclith.adapters.output.memory.repository import InMemoryRepository
from domain.models.ingredient_group import IngredientGroup
from domain.ports.output.ingredient_group_repository import IngredientGroupRepository


class InMemoryIngredientGroupRepository(InMemoryRepository[IngredientGroup], IngredientGroupRepository):
    async def find_by_name(self, name: str) -> list[IngredientGroup]:
        return [item for item in self._store.values() if name.lower() in item.name.lower() and not item.is_deleted]

    async def find_page_by_name(
        self,
        name: str,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[IngredientGroup], int]:
        filtered = [item for item in self._store.values() if name.lower() in item.name.lower() and not item.is_deleted]
        total = len(filtered)
        page = filtered[offset: offset + limit] if limit is not None else filtered[offset:]
        return page, total
