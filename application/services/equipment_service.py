from typing import Any
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from arclith import BaseService, Logger
from domain.models.catalog_normalization import normalize_catalog_name
from domain.models.equipment import Equipment
from domain.models.generated_image import GeneratedImage
from domain.ports.output.image_generator import ImageGenerator
from domain.ports.output.equipment_repository import EquipmentRepository
from uuid6 import UUID


class EquipmentDuplicateMergeError(ValueError):
    """Raised when an equipment duplicate merge cannot be applied."""


class EquipmentImageAlreadyExistsError(ValueError):
    """Raised when image generation would replace an existing image."""


class EquipmentImageGenerationUnavailableError(RuntimeError):
    """Raised when no equipment image generator is configured."""


class EquipmentImageGenerationInProgressError(RuntimeError):
    """Raised when another request already generates an equipment image."""


class EquipmentImageGenerationConflictError(RuntimeError):
    """Raised when an image generation reservation is lost."""


class EquipmentService(BaseService[Equipment]):
    def __init__(
        self,
        repository: EquipmentRepository,
        logger: Logger,
        retention_days: float | None = None,
        image_generator: ImageGenerator | None = None,
    ) -> None:
        super().__init__(repository, logger, retention_days)
        self._equipment_repo = repository
        self._image_generator = image_generator

    @property
    def repository(self) -> EquipmentRepository:
        return self._equipment_repo

    async def generate_main_image(
        self,
        uuid: UUID,
        *,
        replace_existing: bool = False,
    ) -> tuple[Equipment, GeneratedImage]:
        image_generator = self._image_generator
        if image_generator is None:
            raise EquipmentImageGenerationUnavailableError("Equipment image generation is not configured")

        reservation_id = str(uuid4())
        equipment = await self._reserve_image_generation(
            uuid,
            reservation_id,
            replace_existing=replace_existing,
        )
        try:
            generated = await image_generator.generate(
                brief=self._build_image_brief(equipment),
                bucket="equipment",
                object_prefix=f"equipment/{equipment.uuid}/main",
            )
            updated = await self._equipment_repo.complete_image_generation(
                uuid,
                reservation_id,
                generated.image.url,
                replace_existing=replace_existing,
            )
            if updated is None:
                raise EquipmentImageGenerationConflictError(
                    "Equipment changed while its image was being generated"
                )
            return updated, generated
        except BaseException:
            await self._equipment_repo.release_image_generation(uuid, reservation_id)
            raise

    async def _reserve_image_generation(
        self,
        uuid: UUID,
        reservation_id: str,
        *,
        replace_existing: bool,
    ) -> Equipment:
        current = await self.read(uuid)
        self._ensure_image_generation_allowed(current, uuid, replace_existing=replace_existing)
        equipment = await self._equipment_repo.reserve_image_generation(
            uuid,
            reservation_id,
            datetime.now(timezone.utc) + timedelta(minutes=5),
            replace_existing=replace_existing,
        )
        if equipment is not None:
            return equipment
        latest = await self.read(uuid)
        self._ensure_image_generation_allowed(latest, uuid, replace_existing=replace_existing)
        raise EquipmentImageGenerationInProgressError("Equipment image generation is already in progress")

    @staticmethod
    def _ensure_image_generation_allowed(
        equipment: Equipment | None,
        uuid: UUID,
        *,
        replace_existing: bool,
    ) -> None:
        if equipment is None:
            raise KeyError(f"Equipment with uuid {uuid} not found")
        if equipment.main_image and equipment.main_image.strip() and not replace_existing:
            raise EquipmentImageAlreadyExistsError("Equipment already has a main image")

    @staticmethod
    def _build_image_brief(equipment: Equipment) -> str:
        description = (
            f" Détails à respecter : {equipment.description.strip()}."
            if equipment.description and equipment.description.strip()
            else ""
        )
        return (
            "Photographie produit réaliste d'un ustensile ou équipement de cuisine : "
            f"« {equipment.name.strip()} ».{description} Objet seul, entièrement visible, "
            "fond neutre clair, lumière douce, proportions fidèles, aucun ingrédient, "
            "aucun plat préparé et aucun texte dans l'image."
        )

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
