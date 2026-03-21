from typing import Literal

from arclith import Entity
from pydantic import Field, field_validator

from domain.models import Ingredient
from domain.models.step import Step
from domain.models.ustensil import Ustensil


class Recipe(Entity):
    name: str = Field(
        ...,
        description="Nom de la recette, normalisé (espaces supprimés en début et fin).",
        examples=["Recette de pizza", "Recette de salade"]
    )

    description: str | None = Field(
        None,
        description="Description détaillée de la recette. None si non applicable.",
        examples=["Recette de pizza", "Recette de salade"]
    )

    ingredients: list[Ingredient] | None = Field(
        None,
        description="Liste des ingrédients nécessaires pour la recette. None si non applicable.")

    ustensils: list[Ustensil] | None = Field(None, description="Liste des ustensiles nécessaires pour la recette.")

    nutriscore: Literal["A", "B", "C", "D", "E", "F"] | None = Field(
        None,
        description="Nutriscore de la recette. None si non applicable.", examples=["A", "B", "C", "D", "E", "F"])

    steps: list[Step] | None = Field(None, description="Liste des étapes nécessaires pour la recette.")

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Ingredient name cannot be empty")
        return stripped

    def model_post_init(self, __context) -> None:
        """Assign recipe_uuid to all steps after model initialization."""
        super().model_post_init(__context)
        if self.steps:
            for step in self.steps:
                if step.recipe_uuid is None:
                    step.recipe_uuid = self.uuid


