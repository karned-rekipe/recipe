from pydantic import Field, field_validator

from arclith.domain.models.entity import Entity


class Ingredient(Entity):
    name: str = Field(
        ...,
        description="Ingredient name, normalized (leading/trailing spaces removed).",
        examples=["Tomate", "Farine de blé"],
    )
    rayon: str | None = Field(
        None,
        description="Shelf/aisle category.",
        examples=["fruits et légumes", "boucherie"],
    )
    group: str | None = Field(
        None,
        description="Food group.",
        examples=["légumes", "protéines", "féculents"],
    )
    green_score: int | None = Field(
        None,
        description="Environmental score (OpenFoodFacts scale).",
        ge=0,
        examples=[80, 45],
    )
    unit: str | None = Field(
        None,
        description="Unit of measure.",
        examples=["g", "ml", "pièce"],
    )
    quantity: float | None = Field(
        None,
        description="Default quantity.",
        ge=0,
        examples=[100.0, 1.0],
    )
    season_months: dict[int, int] = Field(
        default_factory=dict,
        description="Seasonality map: month (1-12) → score (1-3), 3 = peak season. Empty = year-round.",
        examples=[{6: 2, 7: 3, 8: 3, 9: 2}],
    )

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Ingredient name cannot be empty")
        return stripped

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
