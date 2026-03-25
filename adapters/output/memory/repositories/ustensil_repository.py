from arclith.adapters.output.memory.repository import InMemoryRepository

from domain.models.ustensil import Ustensil
from domain.ports.output.ustensil_repository import UstensilRepository


class InMemoryUstensilRepository(InMemoryRepository[Ustensil], UstensilRepository):
    async def find_by_name(self, name: str) -> list[Ustensil]:
        return [i for i in self._store.values() if name.lower() in i.name.lower()]
