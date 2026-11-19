from abc import abstractmethod

from arclith.domain.ports.repository import Repository
from domain.models.equipment import Equipment


class EquipmentRepository(Repository[Equipment]):
    @abstractmethod
    async def find_by_name(self, name: str) -> list[Equipment]:
        pass

    @abstractmethod
    async def find_page_by_name(self, name: str, offset: int = 0, limit: int | None = None) -> tuple[list[Equipment], int]:
        """Return a page of equipment matching name filter and the total count."""
        pass
