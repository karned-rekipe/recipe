from datetime import datetime, timezone

from arclith.adapters.output.memory.repository import InMemoryRepository
from domain.models.equipment import Equipment
from domain.ports.output.equipment_repository import EquipmentRepository
from uuid6 import UUID


class InMemoryEquipmentRepository(InMemoryRepository[Equipment], EquipmentRepository):
    def __init__(self) -> None:
        super().__init__()
        self._image_generation_reservations: dict[UUID, tuple[str, datetime]] = {}

    async def reserve_image_generation(
        self,
        equipment_uuid: UUID,
        reservation_id: str,
        expires_at: datetime,
        *,
        replace_existing: bool,
    ) -> Equipment | None:
        now = datetime.now(timezone.utc)
        reservation = self._image_generation_reservations.get(equipment_uuid)
        if reservation is not None and reservation[1] > now:
            return None
        equipment = self._store.get(equipment_uuid)
        if equipment is None or equipment.is_deleted:
            return None
        if equipment.main_image and equipment.main_image.strip() and not replace_existing:
            return None
        self._image_generation_reservations[equipment_uuid] = (reservation_id, expires_at)
        return equipment

    async def complete_image_generation(
        self,
        equipment_uuid: UUID,
        reservation_id: str,
        image_url: str,
        *,
        replace_existing: bool,
    ) -> Equipment | None:
        reservation = self._image_generation_reservations.get(equipment_uuid)
        equipment = self._store.get(equipment_uuid)
        if reservation is None or reservation[0] != reservation_id or equipment is None:
            return None
        if equipment.main_image and equipment.main_image.strip() and not replace_existing:
            return None
        updated = equipment.model_copy(update={
            "main_image": image_url,
            "updated_at": datetime.now(timezone.utc),
            "version": equipment.version + 1,
        })
        self._store[equipment_uuid] = updated
        self._image_generation_reservations.pop(equipment_uuid, None)
        return updated

    async def release_image_generation(self, equipment_uuid: UUID, reservation_id: str) -> None:
        reservation = self._image_generation_reservations.get(equipment_uuid)
        if reservation is not None and reservation[0] == reservation_id:
            self._image_generation_reservations.pop(equipment_uuid, None)

    async def find_by_name(self, name: str) -> list[Equipment]:
        return [i for i in self._store.values() if name.lower() in i.name.lower() and not i.is_deleted]

    async def find_page_by_name(self, name: str, offset: int = 0, limit: int | None = None) -> tuple[list[Equipment], int]:
        filtered = [i for i in self._store.values() if name.lower() in i.name.lower() and not i.is_deleted]
        total = len(filtered)
        page = filtered[offset: offset + limit] if limit is not None else filtered[offset:]
        return page, total
