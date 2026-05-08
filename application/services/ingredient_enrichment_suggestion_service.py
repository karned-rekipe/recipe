import json
from datetime import UTC, datetime
from typing import Any

from arclith import BaseService, Logger
from domain.models.ingredient import EnrichmentProfile, Ingredient
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
        existing = await self._find_equivalent_pending_suggestion(entity)
        if existing is not None:
            await self._mark_ingredient_as_suggested(ingredient, entity.proposed_patch)
            return existing

        created = await super().create(entity)
        await self._mark_ingredient_as_suggested(ingredient, created.proposed_patch)
        return created

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

        requested_fields = self._select_requested_fields(suggestion, fields)
        rejected_fields = set(suggestion.rejected_fields)
        applicable_patch: dict[str, Any] = {}
        skipped_fields: list[str] = []
        for field_name, value in suggestion.proposed_patch.items():
            if field_name not in requested_fields or field_name in rejected_fields:
                continue
            if not force and self._is_validated_field(ingredient, field_name):
                skipped_fields.append(field_name)
                continue
            applicable_patch[field_name] = value

        if applicable_patch:
            updated_payload = ingredient.model_dump(mode="python", exclude_computed_fields=True)
            updated_payload.update(applicable_patch)
            await self._ingredient_repo.update(Ingredient.model_validate(updated_payload))

        applied_fields = self._merge_fields(suggestion.applied_fields, applicable_patch)
        new_status = self._status_from_field_sets(suggestion, applied_fields, suggestion.rejected_fields)
        if skipped_fields and new_status == "pending":
            new_status = "partially_applied"
        updated = suggestion.model_copy(
            update={
                "status": new_status,
                "applied_fields": applied_fields,
                "applied_at": datetime.now(UTC) if applicable_patch else suggestion.applied_at,
            }
        )
        self._logger.info(
            "Ingredient enrichment suggestion applied",
            ingredient_uuid=str(ingredient_uuid),
            suggestion_uuid=str(suggestion_uuid),
            applied_fields=list(applicable_patch),
            skipped_fields=skipped_fields,
        )
        return await self._suggestion_repo.update(updated)

    async def reject(
        self,
        ingredient_uuid: UUID,
        suggestion_uuid: UUID,
        fields: list[str] | None = None,
    ) -> IngredientEnrichmentSuggestion:
        ingredient = await self._read_ingredient(ingredient_uuid)
        suggestion = await self._read_suggestion(ingredient_uuid, suggestion_uuid)
        if suggestion.status not in {"pending", "partially_applied"}:
            raise IngredientEnrichmentSuggestionError(f"Suggestion status does not allow reject: {suggestion.status}")

        requested_fields = self._select_requested_fields(suggestion, fields)
        rejected_fields = self._merge_fields(suggestion.rejected_fields, requested_fields)
        updated_ingredient = ingredient.model_copy(
            update={
                "enrichment_profile": ingredient.enrichment_profile.model_copy(
                    update={
                        "rejected_fields": self._merge_fields(
                            ingredient.enrichment_profile.rejected_fields,
                            requested_fields,
                        )
                    }
                )
            }
        )
        await self._ingredient_repo.update(updated_ingredient)

        new_status = self._status_from_field_sets(suggestion, suggestion.applied_fields, rejected_fields)
        updated = suggestion.model_copy(
            update={
                "status": new_status,
                "rejected_fields": rejected_fields,
                "rejected_at": datetime.now(UTC) if new_status == "rejected" else suggestion.rejected_at,
            }
        )
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

    @staticmethod
    def _select_requested_fields(
        suggestion: IngredientEnrichmentSuggestion,
        fields: list[str] | None,
    ) -> set[str]:
        proposed_fields = set(suggestion.proposed_patch)
        if fields is None:
            return proposed_fields
        requested_fields = set(fields)
        unknown_fields = requested_fields - proposed_fields
        if unknown_fields:
            raise IngredientEnrichmentSuggestionError(
                f"Fields are not part of this suggestion: {', '.join(sorted(unknown_fields))}"
            )
        return requested_fields

    @staticmethod
    def _merge_fields(existing_fields: list[str], new_fields: set[str] | dict[str, Any]) -> list[str]:
        return sorted(set(existing_fields) | set(new_fields))

    @staticmethod
    def _status_from_field_sets(
        suggestion: IngredientEnrichmentSuggestion,
        applied_fields: list[str],
        rejected_fields: list[str],
    ) -> str:
        proposed_fields = set(suggestion.proposed_patch)
        applied = set(applied_fields)
        rejected = set(rejected_fields)
        resolved = applied | rejected
        if proposed_fields and proposed_fields <= rejected:
            return "rejected"
        if proposed_fields and proposed_fields <= applied:
            return "applied"
        if resolved:
            return "partially_applied"
        return "pending"

    async def _find_equivalent_pending_suggestion(
        self,
        suggestion: IngredientEnrichmentSuggestion,
    ) -> IngredientEnrichmentSuggestion | None:
        proposed_fingerprint = self._patch_fingerprint(suggestion.proposed_patch)
        for existing in await self._suggestion_repo.find_pending_by_ingredient_uuid(suggestion.ingredient_uuid):
            if self._patch_fingerprint(existing.proposed_patch) == proposed_fingerprint:
                return existing
        return None

    async def _mark_ingredient_as_suggested(
        self,
        ingredient: Ingredient,
        proposed_patch: dict[str, Any],
    ) -> None:
        enrichment_profile = proposed_patch.get("enrichment_profile")
        if not isinstance(enrichment_profile, dict):
            return

        profile_payload = ingredient.enrichment_profile.model_dump(mode="python")
        profile_payload.update(enrichment_profile)
        updated_ingredient = ingredient.model_copy(
            update={
                "enrichment_profile": EnrichmentProfile.model_validate(profile_payload),
            }
        )
        await self._ingredient_repo.update(updated_ingredient)

    @classmethod
    def _patch_fingerprint(cls, patch: dict[str, Any]) -> str:
        normalized = cls._normalize_patch_for_idempotency(patch)
        return json.dumps(normalized, default=str, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _normalize_patch_for_idempotency(patch: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(patch)
        enrichment_profile = normalized.get("enrichment_profile")
        if isinstance(enrichment_profile, dict):
            normalized_profile = dict(enrichment_profile)
            normalized_profile.pop("last_run_uuid", None)
            normalized_profile.pop("last_enriched_at", None)
            normalized["enrichment_profile"] = normalized_profile
        return normalized
