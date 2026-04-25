from pydantic import BaseModel, Field, field_validator
from uuid import UUID


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

    @field_validator("ingredient_uuid", mode="before")
    @classmethod
    def coerce_uuid(cls, v: object) -> UUID:
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
