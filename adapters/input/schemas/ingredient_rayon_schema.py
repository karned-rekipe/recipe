from uuid import UUID as StdUUID

from pydantic import BaseModel, Field, field_validator

from arclith.adapters.input.schemas.base_schema import BaseSchema


class IngredientRayonCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, examples=["Frais"])
    slug: str | None = None
    description: str | None = None
    sort_order: int = Field(0, ge=0)

    @field_validator("name", mode="before")
    @classmethod
    def name_not_empty(cls, value: str) -> str:
        if isinstance(value, str) and not value.strip():
            raise ValueError("Name cannot be empty")
        return value


class IngredientRayonPatchSchema(BaseModel):
    name: str | None = Field(None, min_length=1)
    slug: str | None = None
    description: str | None = None
    sort_order: int | None = Field(None, ge=0)


class IngredientRayonUpdateSchema(IngredientRayonCreateSchema):
    pass


class IngredientRayonCreatedSchema(BaseModel):
    uuid: StdUUID


class IngredientRayonSchema(BaseSchema):
    name: str
    slug: str
    description: str | None = None
    sort_order: int = 0
