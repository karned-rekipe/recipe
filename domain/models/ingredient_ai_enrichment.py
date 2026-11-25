from typing import Literal

from pydantic import BaseModel, Field


class IngredientAIEnrichment(BaseModel):
    """Validated outcome returned by the internal ingredient agent."""

    run_uuid: str = Field(min_length=1)
    ingredient_uuid: str = Field(min_length=1)
    suggestion_uuid: str | None = None
    status: Literal["success"]
    completeness_score: int = Field(ge=0, le=100)
    missing_fields: list[str] = Field(default_factory=list)
    proposed_fields: list[str] = Field(default_factory=list)
    image_generated: bool = False
    warnings: list[str] = Field(default_factory=list)
