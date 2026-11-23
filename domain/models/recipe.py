from collections.abc import Iterable
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from arclith.domain.models.entity import Entity
from domain.models.country import Country
from domain.models.meal_category import MealCategory
from domain.models.recipe_component import RecipeComponent
from domain.models.recipe_equipment import RecipeEquipment
from domain.models.recipe_ingredient import RecipeIngredient
from domain.models.step import Step
from uuid6 import UUID


class MealType(str, Enum):
    breakfast = "breakfast"
    lunch = "lunch"
    snack = "snack"
    dinner = "dinner"


class RecipeStatus(str, Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class RecipeQualityStatus(str, Enum):
    minimal = "minimal"
    text_only = "text_only"
    structured = "structured"
    validated = "validated"


class Source(BaseModel):
    name: str
    description: str | None = None
    uri: str | None = None


class Recipe(Entity):
    name: str = Field(
        ...,
        description="Recipe name, normalized (leading/trailing spaces removed).",
        examples=["recipe 1", "recipe 2"],
    )
    subtitle: str | None = Field(
        None,
        description="Optional editorial subtitle displayed separately from the recipe name.",
        max_length=160,
        examples=["Tarte citron meringuée"],
    )
    description: str | None = Field(
        None,
        description="Detailed description of the recipe.",
        examples=["Pizza recipe", "Salad recipe"],
    )
    origin_country: Country | None = Field(
        None,
        description="Country of origin (ISO 3166-1 alpha-2 code).",
        examples=["FR", "ES", "IT"],
    )
    meal_type: MealType | None = Field(None, description="Indicative meal type.", examples=["dinner", "lunch"])
    meal_category: MealCategory | None = Field(None, description="Indicative course in the meal.", examples=["first_course", "dessert"])
    servings: int | None = Field(None, description="Number of servings.", ge=1, examples=[4, 6])
    unit_count: int | None = Field(None, description="Number of units.", ge=1, examples=[12, 8])
    difficulty: int | None = Field(None, description="Difficulty level from 1 to 5.", ge=1, le=5, examples=[3])
    price: int | None = Field(None, description="Price level from 1 to 5.", ge=1, le=5, examples=[2])
    sources: list[Source] = Field(default_factory=list, description="List of sources.", examples=[[{"name": "Marmiton", "description": "Original recipe", "uri": "https://www.marmiton.org/recettes/recette_pizza.html"}]])
    secondary_images: list[str] = Field(default_factory=list, description="Secondary image URIs.", examples=[["https://example.com/pizza2.jpg", "https://example.com/pizza3.jpg"]])
    main_image: str | None = Field(None, description="Main image URI.", examples=["https://example.com/pizza.jpg"])
    favorite: bool = Field(False, description="Whether the recipe was marked as a favorite.")
    tag_uuids: list[UUID] = Field(default_factory=list, description="Referenced tag UUIDs.")
    season_months: dict[int, int] = Field(
        default_factory=dict,
        description="Computed recipe seasonality map: month (1-12) -> score (1-3).",
        examples=[{6: 1, 7: 3, 8: 3, 9: 2}],
    )
    status: RecipeStatus = Field(RecipeStatus.active, description="Lifecycle status of the recipe.")
    quality_status: RecipeQualityStatus = Field(
        RecipeQualityStatus.structured,
        description="Migration/completeness quality status for progressive enrichment.",
    )
    legacy_id: int | None = Field(
        None,
        description="Stable identifier from the legacy recipe source.",
        examples=[42],
    )
    created_at_legacy: datetime | None = Field(
        None,
        description="Creation timestamp from the legacy source, when available.",
    )
    updated_at_legacy: datetime | None = Field(
        None,
        description="Last update timestamp from the legacy source, when available.",
    )
    migration_metadata: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description="Technical metadata captured during migration/import runs.",
    )
    components: list[RecipeComponent] = Field(default_factory=list, description="Linked child recipes used as sub-recipes.")
    ingredients: list[RecipeIngredient] = Field(default_factory=list, description="Embedded list of recipe ingredients.")
    equipment: list[RecipeEquipment] = Field(default_factory=list, description="Embedded list of recipe equipment.")
    steps: list[Step] = Field(default_factory=list, description="Ordered list of recipe steps.")

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Recipe name cannot be empty")
        return stripped

    @field_validator("subtitle", mode="before")
    @classmethod
    def normalize_subtitle(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("tag_uuids", mode="before")
    @classmethod
    def coerce_tag_uuids(cls, value: object) -> list[UUID]:
        if value is None:
            return []
        if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
            raise ValueError("tag_uuids must be a list")
        return [item if isinstance(item, UUID) else UUID(str(item)) for item in value]

    @field_validator("season_months", mode="before")
    @classmethod
    def validate_season_months(cls, value: dict) -> dict:
        for month, score in value.items():
            month_int = int(month)
            if not 1 <= month_int <= 12:
                raise ValueError(f"Month key must be between 1 and 12, got {month_int}")
            if not 1 <= int(score) <= 3:
                raise ValueError(f"Season score must be between 1 and 3, got {score}")
        return {int(month): int(score) for month, score in value.items()}
