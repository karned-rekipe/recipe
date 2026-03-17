from abc import abstractmethod

from arclith.domain.ports.repository import Repository
from domain.models.tool import Tool


class ToolRepository(Repository[Tool]):
    @abstractmethod
    async def find_by_name(self, name: str) -> list[Tool]:
        pass
