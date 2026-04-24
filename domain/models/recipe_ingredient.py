from pydantic import BaseModel, Field, field_validator


class RecipeIngredient(BaseModel):
    name: str = Field(
        ...,
        description="Ingredient name, normalized (leading/trailing spaces removed).",
        examples=["Tomate", "Farine de ble"],
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
    season_months: dict[int, int] = Field(
        default_factory=dict,
        description="Seasonality map: month (1-12) -> score (1-3), 3 = peak season. Empty = year-round.",
        examples=[{6: 2, 7: 3, 8: 3, 9: 2}],
    )
    rayon: str | None = Field(
        None,
        description="Shelf/aisle category.",
        examples=["fruits et legumes", "epicerie"],
    )
    group: str | None = Field(
        None,
        description="Food group.",
        examples=["legumes", "proteines", "feculents"],
    )
    green_score: int | None = Field(
        None,
        description="Environmental score (OpenFoodFacts scale).",
        ge=0,
        examples=[80, 45],
    )

    @field_validator("name", "unit", mode="before")
    @classmethod
    def strip_required_text(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field cannot be empty")
        return stripped

    @field_validator("season_months", mode="before")
    @classmethod
    def validate_season_months(cls, v: dict) -> dict[int, int]:
        for month, score in v.items():
            month_int = int(month)
            score_int = int(score)
            if not 1 <= month_int <= 12:
                raise ValueError(f"Month key must be between 1 and 12, got {month_int}")
            if not 1 <= score_int <= 3:
                raise ValueError(f"Season score must be between 1 and 3, got {score_int}")
        return {int(k): int(val) for k, val in v.items()}
