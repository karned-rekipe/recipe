from datetime import datetime
from typing import Any, Literal

from arclith.domain.models.entity import Entity
from pydantic import Field, field_validator
from uuid6 import UUID

SuggestionStatus = Literal["pending", "partially_applied", "applied", "rejected", "expired"]


class IngredientEnrichmentSuggestion(Entity):
    ingredient_uuid: UUID = Field(description="Ingredient targeted by this suggestion.")
    run_uuid: UUID = Field(description="Agent run that produced this suggestion.")
    status: SuggestionStatus = Field(default="pending", description="Suggestion lifecycle status.")
    proposed_patch: dict[str, Any] = Field(default_factory=dict)
    field_confidences: dict[str, float] = Field(default_factory=dict)
    field_sources: dict[str, str] = Field(default_factory=dict)
    reasoning_summary: str = Field(default="")
    applied_at: datetime | None = None
    rejected_at: datetime | None = None

    @field_validator("ingredient_uuid", "run_uuid", mode="before")
    @classmethod
    def coerce_uuid(cls, value: object) -> UUID:
        if isinstance(value, UUID):
            return value
        return UUID(str(value))
