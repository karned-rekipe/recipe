from arclith.adapters.output.memory.repository import InMemoryRepository
from domain.models.tool import Tool
from domain.ports.tool_repository import ToolRepository


class InMemoryToolRepository(InMemoryRepository[Tool], ToolRepository):
    async def find_by_name(self, name: str) -> list[Tool]:
        return [i for i in self._store.values() if name.lower() in i.name.lower()]

