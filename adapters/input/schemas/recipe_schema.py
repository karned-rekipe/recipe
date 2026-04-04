from pydantic import BaseModel, Field, field_validator
from uuid import UUID as StdUUID

from arclith.adapters.input.schemas.base_schema import BaseSchema


class RecipeCreateSchema(BaseModel):
    name: str = Field(
        ...,
        description="Nom de l'ingrédient.",
        examples = ["Farine de blé", "Sel fin"],
        min_length = 1
    )

    @field_validator("name", mode = "before")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if isinstance(v, str) and not v.strip():
            raise ValueError("Name cannot be empty")
        return v


class RecipePatchSchema(RecipeCreateSchema):
    name: str | None = Field(  # type: ignore[assignment]
        None,
        description="Nouveau nom de l'ingrédient. Ignoré si absent.",
        examples=["Farine complète", None],
    )


class RecipeUpdateSchema(RecipeCreateSchema):
    pass


class RecipeCreatedSchema(BaseModel):
    uuid: StdUUID = Field(
        description="Identifiant unique de l'ingrédient créé (UUIDv7).",
        examples=["01951234-5678-7abc-def0-123456789abc"],
    )


class RecipeSchema(BaseSchema):
    name: str = Field(
        ...,
        description = "Nom de l'ingrédient.",
        examples = ["Farine de blé", "Sel fin"],
    )
