from typing import Any

from application.use_cases import FindIngredientByNameUseCase
from arclith import BaseService, Logger
from domain.models.catalog_normalization import normalize_catalog_name
from domain.models.ingredient import Ingredient, MediaProfile
from domain.models.ingredient_ai_enrichment import IngredientAIEnrichment
from domain.models.ingredient_image_generation import IngredientImageGeneration
from domain.models.ingredient_group import IngredientGroup
from domain.models.ingredient_rayon import IngredientRayon
from domain.ports.output.ingredient_group_repository import IngredientGroupRepository
from domain.ports.output.ingredient_enrichment_agent import IngredientEnrichmentAgent
from domain.ports.output.ingredient_image_generation_agent import IngredientImageGenerationAgent
from domain.ports.output.ingredient_repository import IngredientRepository
from domain.ports.output.ingredient_rayon_repository import IngredientRayonRepository
from uuid6 import UUID


class IngredientReferenceError(ValueError):
    """Raised when an ingredient references an unknown catalog setting."""


class IngredientDuplicateMergeError(ValueError):
    """Raised when an ingredient duplicate merge cannot be applied."""


class IngredientUnitConversionError(ValueError):
    """Raised when an ingredient unit conversion cannot be resolved."""


class IngredientImageGenerationUnavailableError(RuntimeError):
    """Raised when the internal ingredient image agent is not configured."""


class IngredientAIEnrichmentUnavailableError(RuntimeError):
    """Raised when the internal ingredient completion agent is not configured."""


GLOBAL_UNITS: tuple[dict[str, str], ...] = (
    {"code": "g", "label": "gramme", "kind": "mass"},
    {"code": "kg", "label": "kilogramme", "kind": "mass"},
    {"code": "ml", "label": "millilitre", "kind": "volume"},
    {"code": "cl", "label": "centilitre", "kind": "volume"},
    {"code": "l", "label": "litre", "kind": "volume"},
    {"code": "piece", "label": "piece", "kind": "count"},
    {"code": "cac", "label": "cuillere a cafe", "kind": "kitchen"},
    {"code": "cas", "label": "cuillere a soupe", "kind": "kitchen"},
    {"code": "pincee", "label": "pincee", "kind": "kitchen"},
    {"code": "verre", "label": "verre", "kind": "kitchen"},
    {"code": "tranche", "label": "tranche", "kind": "kitchen"},
    {"code": "paquet", "label": "paquet", "kind": "purchase"},
    {"code": "boite", "label": "boite", "kind": "purchase"},
    {"code": "bouteille", "label": "bouteille", "kind": "purchase"},
    {"code": "barquette", "label": "barquette", "kind": "purchase"},
    {"code": "serving", "label": "portion", "kind": "business"},
    {"code": "portion", "label": "portion", "kind": "business"},
)

GLOBAL_CONVERSIONS: dict[tuple[str, str], float] = {
    ("kg", "g"): 1000.0,
    ("g", "kg"): 0.001,
    ("l", "ml"): 1000.0,
    ("ml", "l"): 0.001,
    ("cl", "ml"): 10.0,
    ("ml", "cl"): 0.1,
    ("l", "cl"): 100.0,
    ("cl", "l"): 0.01,
}


class IngredientService(BaseService[Ingredient]):
    def __init__(
        self,
        repository: IngredientRepository,
        logger: Logger,
        retention_days: float | None = None,
        group_repository: IngredientGroupRepository | None = None,
        rayon_repository: IngredientRayonRepository | None = None,
        enrichment_agent: IngredientEnrichmentAgent | None = None,
        image_generation_agent: IngredientImageGenerationAgent | None = None,
    ) -> None:
        super().__init__(repository, logger, retention_days)
        self._ingredient_repo = repository
        self._find_by_name_uc = FindIngredientByNameUseCase(repository, logger)
        self._group_repo = group_repository
        self._rayon_repo = rayon_repository
        self._enrichment_agent = enrichment_agent or image_generation_agent

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

    async def generate_main_image_suggestion(self, uuid: UUID) -> IngredientImageGeneration:
        agent = self._enrichment_agent
        if agent is None:
            raise IngredientImageGenerationUnavailableError(
                "Ingredient image generation is not configured"
            )
        ingredient = await self.read(uuid)
        if ingredient is None or ingredient.is_deleted:
            raise KeyError(f"Ingredient with uuid {uuid} not found")

        result = await agent.generate(ingredient_uuid=str(uuid))
        if result.ingredient_uuid != str(uuid):
            raise RuntimeError("Ingredient image agent returned a result for another ingredient")
        return result

    async def complete_with_ai(self, uuid: UUID) -> IngredientAIEnrichment:
        agent = self._enrichment_agent
        if agent is None:
            raise IngredientAIEnrichmentUnavailableError(
                "Ingredient AI enrichment is not configured"
            )
        ingredient = await self.read(uuid)
        if ingredient is None or ingredient.is_deleted:
            raise KeyError(f"Ingredient with uuid {uuid} not found")

        result = await agent.complete(ingredient_uuid=str(uuid))
        if result.ingredient_uuid != str(uuid):
            raise RuntimeError("Ingredient enrichment agent returned a result for another ingredient")
        return result

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

    async def hydrate_ingredient(
        self,
        ingredient: Ingredient,
        suggested_media_profile: MediaProfile | None = None,
    ) -> dict[str, Any]:
        data = ingredient.model_dump(mode="json", exclude_computed_fields=True)
        data["is_deleted"] = ingredient.is_deleted
        data["group"] = self._catalog_payload(await self._read_group(ingredient.group_uuid))
        data["rayon"] = self._catalog_payload(await self._read_rayon(ingredient.rayon_uuid))
        data["suggested_media_profile"] = (
            suggested_media_profile.model_dump(mode="json")
            if suggested_media_profile is not None
            else None
        )
        return data

    async def hydrate_ingredients(
        self,
        ingredients: list[Ingredient],
        suggested_media_profiles: dict[str, MediaProfile] | None = None,
    ) -> list[dict[str, Any]]:
        media_profiles = suggested_media_profiles or {}
        return [
            await self.hydrate_ingredient(
                ingredient,
                media_profiles.get(str(ingredient.uuid)),
            )
            for ingredient in ingredients
        ]

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

    async def list_units(self) -> list[dict[str, str]]:
        return [dict(unit) for unit in GLOBAL_UNITS]

    async def convert_unit(
        self,
        ingredient_uuid: UUID,
        quantity: float,
        from_unit: str,
        to_unit: str,
    ) -> dict[str, Any]:
        ingredient = await self.read(ingredient_uuid)
        if ingredient is None or ingredient.is_deleted:
            raise IngredientUnitConversionError("Ingredient not found")
        factor, source = self._find_conversion_factor(ingredient, from_unit, to_unit)
        return {
            "ingredient_uuid": ingredient.uuid,
            "quantity": quantity,
            "from_unit": from_unit,
            "converted_quantity": quantity * factor,
            "to_unit": to_unit,
            "factor": factor,
            "source": source,
        }

    @staticmethod
    def _find_conversion_factor(ingredient: Ingredient, from_unit: str, to_unit: str) -> tuple[float, str]:
        if from_unit == to_unit:
            return 1.0, "identity"
        global_factor = GLOBAL_CONVERSIONS.get((from_unit, to_unit))
        if global_factor is not None:
            return global_factor, "global"
        for conversion in ingredient.unit_profile.conversions:
            if conversion.from_unit == from_unit and conversion.to_unit == to_unit:
                return conversion.factor, conversion.source
        raise IngredientUnitConversionError(f"No conversion available from {from_unit} to {to_unit}")

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
