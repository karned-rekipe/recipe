from abc import abstractmethod

from uuid6 import UUID
from arclith.domain.ports.repository import Repository
from domain.models.step import Step


class StepRepository(Repository[Step]):
    @abstractmethod
    async def find_by_name(self, name: str) -> list[Step]:
        pass

    @abstractmethod
    async def find_by_recipe(self, recipe_uuid: UUID) -> list[Step]:
        pass

