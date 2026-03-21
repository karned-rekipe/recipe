from typing import Literal
from uuid import UUID as StdUUID

from arclith.adapters.input.schemas.base_schema import BaseSchema
from pydantic import Field, BaseModel

from adapters.input.schemas import IngredientSchema
from adapters.input.schemas.ingredient_schema import IngredientCreateSchema
from adapters.input.schemas.step_schema import StepSchema, StepCreateSchema
from adapters.input.schemas.ustensil_schema import UstensilSchema, UstensilCreateSchema


class RecipeCreateSchema(BaseModel):
    name: str = Field(
        ...,
        description="Nom de la recette.",
        examples=["Pizza", "Salade"])
    description: str | None = Field(
        None,
        description="Description détaillée de la recette. None si non applicable.",
        examples=["Recette de pizza", "Recette de salade"])
    ingredients: list[IngredientCreateSchema] | None = Field(
        None,
        description="Liste des ingrédients nécessaires pour la recette. None si non applicable.")
    ustensils: list[UstensilCreateSchema] | None = Field(
        None,
        description="Liste des ustensiles nécessaires pour la recette.")
    steps: list[StepCreateSchema] | None = Field(None, description="Liste des étapes nécessaires pour la recette.")
    nutriscore: Literal["A", "B", "C", "D", "E", "F"] | None = Field(
        None,
        description="Nutriscore de la recette. None si non applicable.",
        examples=["A", "B", "C", "D", "E", "F"])


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
    ingredients: list[IngredientSchema] | None = Field(
        None,
        description="Liste des ingrédients nécessaires pour la recette. None si non applicable.")
    ustensils: list[UstensilSchema] | None = Field(
        None,
        description="Liste des ustensiles nécessaires pour la recette.")
    steps: list[StepSchema] | None = Field(None, description="Liste des étapes nécessaires pour la recette.")
    nutriscore: Literal["A", "B", "C", "D", "E", "F"] | None = Field(
        None,
        description="Nutriscore de la recette. None si non applicable.",
        examples=["A", "B", "C", "D", "E", "F"])
