from typing import Self

from pydantic import Field, field_validator, model_validator

from arclith.domain.models.entity import Entity
from domain.models.slug import slugify


class IngredientRayon(Entity):
    name: str = Field(..., description="Ingredient shelf/aisle name.", examples=["Frais"])
    slug: str = Field("", description="Stable normalized shelf/aisle identifier.", examples=["frais"])
    description: str | None = Field(None, description="Optional shelf/aisle description.")
    sort_order: int = Field(0, description="Display order.", ge=0)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Ingredient rayon name cannot be empty")
        return stripped

    @model_validator(mode="after")
    def normalize_slug(self) -> Self:
        self.slug = slugify(self.slug or self.name)
        return self
