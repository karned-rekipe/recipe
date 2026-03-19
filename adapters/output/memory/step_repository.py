from arclith.adapters.output.memory.repository import InMemoryRepository
from domain.models.step import Step
from domain.ports.step_repository import StepRepository


class InMemoryStepRepository(InMemoryRepository[Step], StepRepository):
    async def find_by_name(self, name: str) -> list[Step]:
        return [i for i in self._store.values() if name.lower() in i.name.lower()]

