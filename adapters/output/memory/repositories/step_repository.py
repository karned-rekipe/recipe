from arclith.adapters.output.memory.repository import InMemoryRepository
from uuid6 import UUID

from domain.models.step import Step
from domain.ports.output.step_repository import StepRepository


class InMemoryStepRepository(InMemoryRepository[Step], StepRepository):
    async def find_by_name(self, name: str) -> list[Step]:
        return [i for i in self._store.values() if name.lower() in i.name.lower()]

    async def find_by_recipe(self, recipe_uuid: UUID) -> list[Step]:
        return [i for i in self._store.values() if i.recipe_uuid == recipe_uuid and not i.is_deleted]
