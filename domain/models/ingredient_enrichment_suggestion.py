from datetime import datetime
from typing import Any, Literal

from arclith.domain.models.entity import Entity
from pydantic import Field, field_validator
from uuid6 import UUID

SuggestionStatus = Literal["pending", "partially_applied", "applied", "rejected", "expired"]
_ENRICHABLE_FIELDS = frozenset({
    "media_profile",
    "seasonality_profile",
    "nutrition_profile",
    "sustainability_profile",
    "allergen_profile",
    "unit_profile",
    "package_profiles",
    "substitution_profile",
    "enrichment_profile",
})


class IngredientEnrichmentSuggestion(Entity):
    ingredient_uuid: UUID = Field(description="Ingredient targeted by this suggestion.")
    run_uuid: UUID = Field(description="Agent run that produced this suggestion.")
    status: SuggestionStatus = Field(default="pending", description="Suggestion lifecycle status.")
    proposed_patch: dict[str, Any] = Field(default_factory=dict)
    field_confidences: dict[str, float] = Field(default_factory=dict)
    field_sources: dict[str, str] = Field(default_factory=dict)
    applied_fields: list[str] = Field(default_factory=list)
    rejected_fields: list[str] = Field(default_factory=list)
    reasoning_summary: str = Field(default="")
    applied_at: datetime | None = None
    rejected_at: datetime | None = None

    @field_validator("ingredient_uuid", "run_uuid", mode="before")
    @classmethod
    def coerce_uuid(cls, value: object) -> UUID:
        if isinstance(value, UUID):
            return value
        return UUID(str(value))

    @field_validator("proposed_patch")
    @classmethod
    def validate_enrichable_fields(cls, value: dict[str, Any]) -> dict[str, Any]:
        forbidden = set(value) - _ENRICHABLE_FIELDS
        if forbidden:
            raise ValueError(f"Unsupported enrichment fields: {', '.join(sorted(forbidden))}")
        return value
