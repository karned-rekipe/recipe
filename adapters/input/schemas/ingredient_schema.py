from pydantic import BaseModel, Field, field_validator
from uuid import UUID as StdUUID

from arclith.adapters.input.schemas.base_schema import BaseSchema


class IngredientCreateSchema(BaseModel):
    name: str = Field(
        ...,
        description="Ingredient name.",
        examples=["Tomate", "Farine de blé"],
        min_length=1,
    )
    rayon: str | None = Field(None, description="Shelf/aisle category.", examples=["fruits et légumes"])
    group: str | None = Field(None, description="Food group.", examples=["légumes", "protéines"])
    green_score: int | None = Field(None, description="Environmental score (OpenFoodFacts scale).", ge=0, examples=[80])
    unit: str | None = Field(None, description="Unit of measure.", examples=["g", "ml", "pièce"])
    quantity: float | None = Field(None, description="Default quantity.", ge=0, examples=[100.0])
    season_months: dict[int, int] = Field(
        default_factory=dict,
        description="Seasonality map: month (1-12) → score (1-3), 3 = peak season.",
        examples=[{6: 2, 7: 3, 8: 3, 9: 2}],
    )

    @field_validator("name", mode="before")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if isinstance(v, str) and not v.strip():
            raise ValueError("Name cannot be empty")
        return v

    @field_validator("season_months", mode="before")
    @classmethod
    def validate_season_months(cls, v: dict) -> dict:
        for month, score in v.items():
            month_int = int(month)
            if not 1 <= month_int <= 12:
                raise ValueError(f"Month key must be between 1 and 12, got {month_int}")
            if not 1 <= int(score) <= 3:
                raise ValueError(f"Season score must be between 1 and 3, got {score}")
        return {int(k): int(val) for k, val in v.items()}


class IngredientPatchSchema(BaseModel):
    name: str | None = Field(None, description="New ingredient name.", min_length=1, examples=["Farine complète"])
    rayon: str | None = Field(None, description="Shelf/aisle category.", examples=["épicerie"])
    group: str | None = Field(None, description="Food group.", examples=["féculents"])
    green_score: int | None = Field(None, description="Environmental score.", ge=0, examples=[60])
    unit: str | None = Field(None, description="Unit of measure.", examples=["kg"])
    quantity: float | None = Field(None, description="Default quantity.", ge=0, examples=[500.0])
    season_months: dict[int, int] | None = Field(None, description="Seasonality map.")

    @field_validator("season_months", mode="before")
    @classmethod
    def validate_season_months(cls, v: dict | None) -> dict | None:
        if v is None:
            return v
        for month, score in v.items():
            month_int = int(month)
            if not 1 <= month_int <= 12:
                raise ValueError(f"Month key must be between 1 and 12, got {month_int}")
            if not 1 <= int(score) <= 3:
                raise ValueError(f"Season score must be between 1 and 3, got {score}")
        return {int(k): int(val) for k, val in v.items()}


class IngredientUpdateSchema(IngredientCreateSchema):
    pass


class IngredientCreatedSchema(BaseModel):
    uuid: StdUUID = Field(
        description="Unique identifier of the created ingredient (UUIDv7).",
        examples=["01951234-5678-7abc-def0-123456789abc"],
    )


class IngredientSchema(BaseSchema):
    name: str = Field(..., description="Ingredient name.", examples=["Tomate"])
    rayon: str | None = Field(None, description="Shelf/aisle category.")
    group: str | None = Field(None, description="Food group.")
    green_score: int | None = Field(None, description="Environmental score.")
    unit: str | None = Field(None, description="Unit of measure.")
    quantity: float | None = Field(None, description="Default quantity.")
    season_months: dict[int, int] = Field(default_factory=dict, description="Seasonality map.")
