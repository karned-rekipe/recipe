from typing import Literal

from pydantic import BaseModel, Field, model_validator


class IngredientImageGeneration(BaseModel):
    """Validated outcome returned by the internal ingredient agent."""

    run_uuid: str = Field(min_length=1)
    ingredient_uuid: str = Field(min_length=1)
    suggestion_uuid: str = Field(min_length=1)
    status: Literal["success"]
    completeness_score: int = Field(ge=0, le=100)
    missing_fields: list[str] = Field(default_factory=list)
    proposed_fields: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def image_only_suggestion(self) -> "IngredientImageGeneration":
        if self.proposed_fields != ["media_profile"]:
            raise ValueError("Ingredient image generation must only propose media_profile")
        return self
