from arclith import Entity
from pydantic import Field, field_validator


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

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Ingredient name cannot be empty")
        return stripped


