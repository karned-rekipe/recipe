from pydantic import Field, BaseModel
from uuid import UUID as StdUUID

from arclith.adapters.input.schemas.base_schema import BaseSchema


class RecipeCreateSchema(BaseModel):
    name: str = Field(
        ...,
        description="Nom de la recette.",
        examples=["Pizza", "Salade"])
    description: str | None = Field(
        None,
        description="Description détaillée de la recette. None si non applicable.",
        examples=["Recette de pizza", "Recette de salade"])


class RecipePatchSchema(RecipeCreateSchema):
    name: str | None = Field(
        None,
        description="Nom de la recette.",
        examples=["Pizza", "Salade"])


class RecipeUpdateSchema(RecipeCreateSchema):
    pass

class RecipeCreatedSchema(BaseModel):
    uuid: StdUUID = Field(
        description="UUID de la recette créée.",
        examples=["123e4567-e89b-12d3-a456-426614174000"])


class RecipeSchema(BaseSchema):
    name: str = Field(
        ...,
        description="Nom de la recette.",
        examples=["Pizza", "Salade"])
    description: str | None = Field(
        None,
        description="Description détaillée de la recette. None si non applicable.",
        examples=["Recette de pizza", "Recette de salade"])

