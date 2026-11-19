from uuid import UUID as StdUUID

from pydantic import BaseModel, Field, field_validator

from arclith.adapters.input.schemas.base_schema import BaseSchema
from domain.models.tag import TagCategory


class TagCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, description="Tag name.", examples=["végan"])
    slug: str | None = Field(None, description="Optional normalized slug.", examples=["vegan"])
    category: TagCategory = Field(TagCategory.other, description="Tag category.")
    color: str | None = Field(None, description="Optional UI color.", examples=["#34c759"])

    @field_validator("name", mode="before")
    @classmethod
    def name_not_empty(cls, value: str) -> str:
        if isinstance(value, str) and not value.strip():
            raise ValueError("Name cannot be empty")
        return value


class TagPatchSchema(BaseModel):
    name: str | None = Field(None, min_length=1)
    slug: str | None = None
    category: TagCategory | None = None
    color: str | None = None


class TagUpdateSchema(TagCreateSchema):
    pass


class TagCreatedSchema(BaseModel):
    uuid: StdUUID


class TagSchema(BaseSchema):
    name: str
    slug: str
    category: TagCategory
    color: str | None = None
