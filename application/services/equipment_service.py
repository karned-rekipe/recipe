from typing import Any

from arclith import BaseService, Logger
from domain.models.catalog_normalization import normalize_catalog_name
from domain.models.equipment import Equipment
from domain.ports.output.equipment_repository import EquipmentRepository
from uuid6 import UUID


class EquipmentDuplicateMergeError(ValueError):
    """Raised when an equipment duplicate merge cannot be applied."""


class EquipmentService(BaseService[Equipment]):
    def __init__(self, repository: EquipmentRepository, logger: Logger, retention_days: float | None = None) -> None:
        super().__init__(repository, logger, retention_days)
        self._equipment_repo = repository

    @property
    def repository(self) -> EquipmentRepository:
        return self._equipment_repo

    async def find_by_name(self, name: str) -> list[Equipment]:
        self._logger.info("🔍 Finding equipment by name", name=name)
        result = [item for item in await self._equipment_repo.find_by_name(name) if not item.is_deleted]
        self._logger.info("✅ Equipment found", name=name, count=len(result))
        return result

    async def find_page_filtered(self, name: str | None = None, offset: int = 0, limit: int | None = None) -> tuple[list[Equipment], int]:
        """Return a page of equipment (optionally filtered by name) and total count."""
        if name:
            return await self._equipment_repo.find_page_by_name(name, offset, limit)
        return await self._equipment_repo.find_page(offset, limit)

    async def find_duplicate_groups(self) -> list[dict[str, Any]]:
        groups: dict[str, list[Equipment]] = {}
        for item in await self.find_all():
            if item.is_deleted:
                continue
            normalized_name = normalize_catalog_name(item.name)
            if not normalized_name:
                continue
            groups.setdefault(normalized_name, []).append(item)

        return [
            {
                "normalized_name": normalized_name,
                "items": [{"uuid": item.uuid, "name": item.name} for item in sorted(items, key=lambda item: item.name.casefold())],
            }
            for normalized_name, items in sorted(groups.items())
            if len(items) > 1
        ]

    async def merge_duplicates(
        self,
        target_uuid: UUID,
        duplicate_uuids: list[UUID],
        recipe_service: Any,
    ) -> dict[str, Any]:
        if any(str(source_uuid) == str(target_uuid) for source_uuid in duplicate_uuids):
            raise EquipmentDuplicateMergeError("Target cannot also be listed as duplicate")

        target = await self.read(target_uuid)
        if target is None or target.is_deleted:
            raise EquipmentDuplicateMergeError("Target equipment does not exist")

        duplicates: list[Equipment] = []
        for duplicate_uuid in duplicate_uuids:
            duplicate = await self.read(duplicate_uuid)
            if duplicate is None or duplicate.is_deleted:
                raise EquipmentDuplicateMergeError(f"Duplicate equipment does not exist: {duplicate_uuid}")
            duplicates.append(duplicate)

        updated_recipe_count = 0
        for duplicate in duplicates:
            updated_recipe_count += await recipe_service.replace_equipment_reference(duplicate.uuid, target.uuid)
            await self.delete(duplicate.uuid)

        return {
            "target_uuid": target.uuid,
            "merged_uuids": [duplicate.uuid for duplicate in duplicates],
            "updated_recipe_count": updated_recipe_count,
            "deleted_count": len(duplicates),
        }
