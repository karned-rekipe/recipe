from abc import abstractmethod

from arclith.domain.ports.repository import Repository
from domain.models.step import Step


class StepRepository(Repository[Step]):
    @abstractmethod
    async def find_by_name(self, name: str) -> list[Step]:
        pass
