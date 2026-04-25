from typing import Any

from application.use_cases import FindIngredientByNameUseCase
from arclith import BaseService, Logger
from domain.models.catalog_normalization import normalize_catalog_name
from domain.models.ingredient import Ingredient
from domain.models.ingredient_group import IngredientGroup
from domain.models.ingredient_rayon import IngredientRayon
from domain.ports.output.ingredient_group_repository import IngredientGroupRepository
from domain.ports.output.ingredient_repository import IngredientRepository
from domain.ports.output.ingredient_rayon_repository import IngredientRayonRepository
from uuid6 import UUID


class IngredientReferenceError(ValueError):
    """Raised when an ingredient references an unknown catalog setting."""


class IngredientDuplicateMergeError(ValueError):
    """Raised when an ingredient duplicate merge cannot be applied."""


class IngredientService(BaseService[Ingredient]):
    def __init__(
        self,
        repository: IngredientRepository,
        logger: Logger,
        retention_days: float | None = None,
        group_repository: IngredientGroupRepository | None = None,
        rayon_repository: IngredientRayonRepository | None = None,
    ) -> None:
        super().__init__(repository, logger, retention_days)
        self._ingredient_repo = repository
        self._find_by_name_uc = FindIngredientByNameUseCase(repository, logger)
        self._group_repo = group_repository
        self._rayon_repo = rayon_repository

    @property
    def repository(self) -> IngredientRepository:
        return self._ingredient_repo

    async def create(self, entity: Ingredient) -> Ingredient:
        await self._ensure_references_exist(entity)
        return await super().create(entity)

    async def update(self, entity: Ingredient) -> Ingredient:
        await self._ensure_references_exist(entity)
        return await super().update(entity)

    async def find_by_name(self, name: str) -> list[Ingredient]:
        return await self._find_by_name_uc.execute(name)

    async def find_page_filtered(
        self,
        name: str | None = None,
        group_uuid: UUID | None = None,
        rayon_uuid: UUID | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Ingredient], int]:
        """Return a page of ingredients (optionally filtered by name) and total count."""
        return await self._ingredient_repo.find_page_filtered(name, group_uuid, rayon_uuid, offset, limit)

    async def hydrate_ingredient(self, ingredient: Ingredient) -> dict[str, Any]:
        data = ingredient.model_dump(mode="json", exclude_computed_fields=True)
        data["is_deleted"] = ingredient.is_deleted
        data["group"] = self._catalog_payload(await self._read_group(ingredient.group_uuid))
        data["rayon"] = self._catalog_payload(await self._read_rayon(ingredient.rayon_uuid))
        return data

    async def hydrate_ingredients(self, ingredients: list[Ingredient]) -> list[dict[str, Any]]:
        return [await self.hydrate_ingredient(ingredient) for ingredient in ingredients]

    async def is_group_used(self, group_uuid: UUID) -> bool:
        return await self._ingredient_repo.exists_by_group_uuid(group_uuid)

    async def is_rayon_used(self, rayon_uuid: UUID) -> bool:
        return await self._ingredient_repo.exists_by_rayon_uuid(rayon_uuid)

    async def find_duplicate_groups(self) -> list[dict[str, Any]]:
        groups: dict[str, list[Ingredient]] = {}
        for ingredient in await self.find_all():
            if ingredient.is_deleted:
                continue
            normalized_name = normalize_catalog_name(ingredient.name)
            if not normalized_name:
                continue
            groups.setdefault(normalized_name, []).append(ingredient)

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
            raise IngredientDuplicateMergeError("Target cannot also be listed as duplicate")

        target = await self.read(target_uuid)
        if target is None or target.is_deleted:
            raise IngredientDuplicateMergeError("Target ingredient does not exist")

        duplicates: list[Ingredient] = []
        for duplicate_uuid in duplicate_uuids:
            duplicate = await self.read(duplicate_uuid)
            if duplicate is None or duplicate.is_deleted:
                raise IngredientDuplicateMergeError(f"Duplicate ingredient does not exist: {duplicate_uuid}")
            duplicates.append(duplicate)

        updated_recipe_count = 0
        for duplicate in duplicates:
            updated_recipe_count += await recipe_service.replace_ingredient_reference(duplicate.uuid, target.uuid)
            await self.delete(duplicate.uuid)

        return {
            "target_uuid": target.uuid,
            "merged_uuids": [duplicate.uuid for duplicate in duplicates],
            "updated_recipe_count": updated_recipe_count,
            "deleted_count": len(duplicates),
        }

    async def _ensure_references_exist(self, ingredient: Ingredient) -> None:
        errors: list[str] = []
        if self._group_repo is not None and ingredient.group_uuid is not None and await self._read_group(ingredient.group_uuid) is None:
            errors.append(f"Unknown ingredient group UUID: {ingredient.group_uuid}")
        if self._rayon_repo is not None and ingredient.rayon_uuid is not None and await self._read_rayon(ingredient.rayon_uuid) is None:
            errors.append(f"Unknown ingredient rayon UUID: {ingredient.rayon_uuid}")
        if errors:
            raise IngredientReferenceError("; ".join(errors))

    async def _read_group(self, group_uuid: UUID | None) -> IngredientGroup | None:
        if self._group_repo is None or group_uuid is None:
            return None
        return await self._group_repo.read(UUID(str(group_uuid)))

    async def _read_rayon(self, rayon_uuid: UUID | None) -> IngredientRayon | None:
        if self._rayon_repo is None or rayon_uuid is None:
            return None
        return await self._rayon_repo.read(UUID(str(rayon_uuid)))

    @staticmethod
    def _catalog_payload(item: IngredientGroup | IngredientRayon | None) -> dict[str, Any] | None:
        if item is None:
            return None
        return item.model_dump(mode="json", exclude_computed_fields=True)
