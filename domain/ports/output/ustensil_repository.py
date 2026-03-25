from abc import abstractmethod
from arclith.domain.ports.repository import Repository

from domain.models.ustensil import Ustensil


class UstensilRepository(Repository[Ustensil]):
    @abstractmethod
    async def find_by_name(self, name: str) -> list[Ustensil]:
        pass
