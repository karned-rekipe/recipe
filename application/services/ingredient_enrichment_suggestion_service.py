from datetime import UTC, datetime
from typing import Any

from arclith import BaseService, Logger
from domain.models.ingredient import Ingredient
from domain.models.ingredient_enrichment_suggestion import IngredientEnrichmentSuggestion
from domain.ports.output.ingredient_enrichment_suggestion_repository import IngredientEnrichmentSuggestionRepository
from domain.ports.output.ingredient_repository import IngredientRepository
from uuid6 import UUID


class IngredientEnrichmentSuggestionError(ValueError):
    """Raised when an enrichment suggestion cannot be applied."""


class IngredientEnrichmentSuggestionService(BaseService[IngredientEnrichmentSuggestion]):
    def __init__(
        self,
        repository: IngredientEnrichmentSuggestionRepository,
        ingredient_repository: IngredientRepository,
        logger: Logger,
        retention_days: float | None = None,
    ) -> None:
        super().__init__(repository, logger, retention_days)
        self._suggestion_repo = repository
        self._ingredient_repo = ingredient_repository
        self._logger = logger

    @property
    def repository(self) -> IngredientEnrichmentSuggestionRepository:
        return self._suggestion_repo

    async def create(self, entity: IngredientEnrichmentSuggestion) -> IngredientEnrichmentSuggestion:
        ingredient = await self._ingredient_repo.read(entity.ingredient_uuid)
        if ingredient is None or ingredient.is_deleted:
            raise IngredientEnrichmentSuggestionError("Ingredient not found")
        return await super().create(entity)

    async def find_by_ingredient_uuid(self, ingredient_uuid: UUID) -> list[IngredientEnrichmentSuggestion]:
        return await self._suggestion_repo.find_by_ingredient_uuid(ingredient_uuid)

    async def apply(
        self,
        ingredient_uuid: UUID,
        suggestion_uuid: UUID,
        fields: list[str] | None = None,
        force: bool = False,
    ) -> IngredientEnrichmentSuggestion:
        ingredient = await self._read_ingredient(ingredient_uuid)
        suggestion = await self._read_suggestion(ingredient_uuid, suggestion_uuid)
        if suggestion.status not in {"pending", "partially_applied"}:
            raise IngredientEnrichmentSuggestionError(f"Suggestion status does not allow apply: {suggestion.status}")

        requested_fields = set(fields or suggestion.proposed_patch)
        applicable_patch: dict[str, Any] = {}
        skipped_fields: list[str] = []
        for field_name, value in suggestion.proposed_patch.items():
            if field_name not in requested_fields:
                continue
            if not force and self._is_validated_field(ingredient, field_name):
                skipped_fields.append(field_name)
                continue
            applicable_patch[field_name] = value

        if applicable_patch:
            updated_payload = ingredient.model_dump(mode="python", exclude_computed_fields=True)
            updated_payload.update(applicable_patch)
            await self._ingredient_repo.update(Ingredient.model_validate(updated_payload))

        new_status = "applied" if applicable_patch and not skipped_fields else "partially_applied"
        updated = suggestion.model_copy(update={"status": new_status, "applied_at": datetime.now(UTC)})
        self._logger.info(
            "Ingredient enrichment suggestion applied",
            ingredient_uuid=str(ingredient_uuid),
            suggestion_uuid=str(suggestion_uuid),
            applied_fields=list(applicable_patch),
            skipped_fields=skipped_fields,
        )
        return await self._suggestion_repo.update(updated)

    async def reject(self, ingredient_uuid: UUID, suggestion_uuid: UUID) -> IngredientEnrichmentSuggestion:
        suggestion = await self._read_suggestion(ingredient_uuid, suggestion_uuid)
        updated = suggestion.model_copy(update={"status": "rejected", "rejected_at": datetime.now(UTC)})
        return await self._suggestion_repo.update(updated)

    async def _read_ingredient(self, ingredient_uuid: UUID) -> Ingredient:
        ingredient = await self._ingredient_repo.read(ingredient_uuid)
        if ingredient is None or ingredient.is_deleted:
            raise IngredientEnrichmentSuggestionError("Ingredient not found")
        return ingredient

    async def _read_suggestion(
        self,
        ingredient_uuid: UUID,
        suggestion_uuid: UUID,
    ) -> IngredientEnrichmentSuggestion:
        suggestion = await self._suggestion_repo.read(suggestion_uuid)
        if suggestion is None or suggestion.is_deleted or str(suggestion.ingredient_uuid) != str(ingredient_uuid):
            raise IngredientEnrichmentSuggestionError("Suggestion not found")
        return suggestion

    @staticmethod
    def _is_validated_field(ingredient: Ingredient, field_name: str) -> bool:
        value = getattr(ingredient, field_name, None)
        validated = getattr(value, "validated", None)
        if validated is not None:
            return bool(validated)
        if field_name == "enrichment_profile":
            return ingredient.enrichment_profile.status == "validated"
        return False
