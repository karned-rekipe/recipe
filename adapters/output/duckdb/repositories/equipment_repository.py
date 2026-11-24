from datetime import datetime, timezone

from arclith.adapters.output.duckdb.repository import DuckDBRepository
from domain.models.equipment import Equipment
from domain.ports.output.equipment_repository import EquipmentRepository
from uuid6 import UUID


class DuckDBEquipmentRepository(DuckDBRepository[Equipment], EquipmentRepository):
    def __init__(self, path: str) -> None:
        super().__init__(path, Equipment)
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
        equipment = await self.read(equipment_uuid)
        if equipment is None or (equipment.main_image and equipment.main_image.strip() and not replace_existing):
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
        equipment = await self.read(equipment_uuid)
        if reservation is None or reservation[0] != reservation_id or equipment is None:
            return None
        if equipment.main_image and equipment.main_image.strip() and not replace_existing:
            return None
        updated = equipment.model_copy(update={
            "main_image": image_url,
            "updated_at": datetime.now(timezone.utc),
            "version": equipment.version + 1,
        })
        await self.update(updated)
        self._image_generation_reservations.pop(equipment_uuid, None)
        return updated

    async def release_image_generation(self, equipment_uuid: UUID, reservation_id: str) -> None:
        reservation = self._image_generation_reservations.get(equipment_uuid)
        if reservation is not None and reservation[0] == reservation_id:
            self._image_generation_reservations.pop(equipment_uuid, None)

    async def find_by_name(self, name: str) -> list[Equipment]:
        rows = self._fetch(
            f"SELECT * FROM {self._table} WHERE deleted_at IS NULL AND lower(name) LIKE ?",  # nosec B608
            [f"%{name.lower()}%"],
        )
        return [self._row_to_entity(r) for r in rows]

    async def find_page_by_name(self, name: str, offset: int = 0, limit: int | None = None) -> tuple[list[Equipment], int]:
        """Single-query pagination with name filter via window function."""
        limit_clause = f"LIMIT {limit}" if limit is not None else ""
        rows = self._fetch(
            f"SELECT *, COUNT(*) OVER () AS __total FROM {self._table} "  # nosec B608
            f"WHERE deleted_at IS NULL AND lower(name) LIKE ? "
            f"ORDER BY rowid OFFSET {offset} {limit_clause}",
            [f"%{name.lower()}%"],
        )
        total = int(rows[0]["__total"]) if rows else 0
        return [self._row_to_entity({k: v for k, v in r.items() if k != "__total"}) for r in rows], total
