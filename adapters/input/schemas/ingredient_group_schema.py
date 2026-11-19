from uuid import UUID as StdUUID

from pydantic import BaseModel, Field, field_validator

from arclith.adapters.input.schemas.base_schema import BaseSchema


class IngredientGroupCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, examples=["Légumes"])
    slug: str | None = None
    description: str | None = None
    sort_order: int = Field(0, ge=0)

    @field_validator("name", mode="before")
    @classmethod
    def name_not_empty(cls, value: str) -> str:
        if isinstance(value, str) and not value.strip():
            raise ValueError("Name cannot be empty")
        return value


class IngredientGroupPatchSchema(BaseModel):
    name: str | None = Field(None, min_length=1)
    slug: str | None = None
    description: str | None = None
    sort_order: int | None = Field(None, ge=0)


class IngredientGroupUpdateSchema(IngredientGroupCreateSchema):
    pass


class IngredientGroupCreatedSchema(BaseModel):
    uuid: StdUUID


class IngredientGroupSchema(BaseSchema):
    name: str
    slug: str
    description: str | None = None
    sort_order: int = 0
