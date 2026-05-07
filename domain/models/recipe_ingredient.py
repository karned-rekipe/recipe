from pydantic import BaseModel, Field, field_validator
from uuid import UUID

from domain.models.recipe_line_origin import RecipeLineOrigin


class RecipeIngredient(BaseModel):
    ingredient_uuid: UUID = Field(
        ...,
        description="Reference to the ingredient catalog item.",
        examples=["01951234-5678-7abc-def0-123456789abc"],
    )
    quantity: float = Field(
        ...,
        description="Quantity required for the recipe.",
        gt=0,
        examples=[100.0, 1.0],
    )
    unit: str = Field(
        ...,
        description="Unit of measure for the recipe quantity.",
        examples=["g", "ml", "piece"],
    )
    component_uuid: UUID | None = Field(
        None,
        description="Parent embedded component UUID when this line is projected from a sub-recipe.",
    )
    source_recipe_uuid: UUID | None = Field(
        None,
        description="Child recipe UUID when this line is projected from a sub-recipe.",
    )
    line_origin: RecipeLineOrigin = Field(
        RecipeLineOrigin.manual,
        description="Whether the line is manually owned by the recipe or projected from a component.",
    )

    @field_validator("ingredient_uuid", "component_uuid", "source_recipe_uuid", mode="before")
    @classmethod
    def coerce_uuid(cls, v: object) -> UUID | None:
        if v is None:
            return None
        if isinstance(v, UUID):
            return v
        return UUID(str(v))

    @field_validator("unit", mode="before")
    @classmethod
    def strip_required_text(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Unit cannot be empty")
        return stripped
