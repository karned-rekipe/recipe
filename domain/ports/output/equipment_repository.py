from abc import abstractmethod
from datetime import datetime

from arclith.domain.ports.repository import Repository
from domain.models.equipment import Equipment
from uuid6 import UUID


class EquipmentRepository(Repository[Equipment]):
    @abstractmethod
    async def reserve_image_generation(
        self,
        equipment_uuid: UUID,
        reservation_id: str,
        expires_at: datetime,
        *,
        replace_existing: bool,
    ) -> Equipment | None:
        """Atomically reserve image generation and return the equipment."""
        pass

    @abstractmethod
    async def complete_image_generation(
        self,
        equipment_uuid: UUID,
        reservation_id: str,
        image_url: str,
        *,
        replace_existing: bool,
    ) -> Equipment | None:
        """Attach the image when the caller still owns the reservation."""
        pass

    @abstractmethod
    async def release_image_generation(self, equipment_uuid: UUID, reservation_id: str) -> None:
        """Release an owned reservation after a failed generation."""
        pass

    @abstractmethod
    async def find_by_name(self, name: str) -> list[Equipment]:
        pass

    @abstractmethod
    async def find_page_by_name(self, name: str, offset: int = 0, limit: int | None = None) -> tuple[list[Equipment], int]:
        """Return a page of equipment matching name filter and the total count."""
        pass
