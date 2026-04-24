from pydantic import BaseModel, Field, field_validator


class RecipeEquipment(BaseModel):
    name: str = Field(
        ...,
        description="Equipment name, normalized (leading/trailing spaces removed).",
        examples=["Four", "Casserole"],
    )
    quantity: float | None = Field(
        None,
        description="Optional quantity of required equipment.",
        ge=0,
        examples=[1.0, 2.0],
    )

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Equipment name cannot be empty")
        return stripped
