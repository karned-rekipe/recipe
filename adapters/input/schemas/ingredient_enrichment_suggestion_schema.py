from datetime import datetime
from typing import Any, Literal
from uuid import UUID as StdUUID

from arclith.adapters.input.schemas.base_schema import BaseSchema
from pydantic import BaseModel, Field

SuggestionStatusSchema = Literal["pending", "partially_applied", "applied", "rejected", "expired"]


class IngredientEnrichmentSuggestionCreateSchema(BaseModel):
    run_uuid: StdUUID
    proposed_patch: dict[str, Any] = Field(default_factory=dict)
    field_confidences: dict[str, float] = Field(default_factory=dict)
    field_sources: dict[str, str] = Field(default_factory=dict)
    reasoning_summary: str = ""


class IngredientEnrichmentSuggestionActionSchema(BaseModel):
    fields: list[str] | None = None
    force: bool = False


class IngredientEnrichmentSuggestionCreatedSchema(BaseModel):
    uuid: StdUUID


class IngredientEnrichmentSuggestionSchema(BaseSchema):
    ingredient_uuid: StdUUID
    run_uuid: StdUUID
    status: SuggestionStatusSchema
    proposed_patch: dict[str, Any] = Field(default_factory=dict)
    field_confidences: dict[str, float] = Field(default_factory=dict)
    field_sources: dict[str, str] = Field(default_factory=dict)
    reasoning_summary: str = ""
    applied_at: datetime | None = None
    rejected_at: datetime | None = None
