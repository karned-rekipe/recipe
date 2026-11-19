from enum import Enum
from typing import Self

from pydantic import Field, field_validator, model_validator

from arclith.domain.models.entity import Entity
from domain.models.slug import slugify


class TagCategory(str, Enum):
    diet = "diet"
    occasion = "occasion"
    service = "service"
    technique = "technique"
    other = "other"


class Tag(Entity):
    name: str = Field(..., description="Tag display name.", examples=["végan", "grande tablée"])
    slug: str = Field("", description="Stable normalized tag identifier.", examples=["vegan"])
    category: TagCategory = Field(TagCategory.other, description="Tag category.")
    color: str | None = Field(None, description="Optional UI color, as a hex value.", examples=["#34c759"])

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Tag name cannot be empty")
        return stripped

    @field_validator("color", mode="before")
    @classmethod
    def normalize_color(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def normalize_slug(self) -> Self:
        self.slug = slugify(self.slug or self.name)
        return self
