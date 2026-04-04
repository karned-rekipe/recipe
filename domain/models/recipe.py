from enum import Enum

from pydantic import BaseModel, Field, computed_field, field_validator

from arclith.domain.models.entity import Entity
from domain.models.country import Country
from domain.models.meal_category import MealCategory
from domain.models.step import Step


class MealType(str, Enum):
    breakfast = "breakfast"
    lunch = "lunch"
    snack = "snack"
    dinner = "dinner"


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
    steps: list[Step] = Field(default_factory=list, description="Ordered list of recipe steps.")

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Recipe name cannot be empty")
        return stripped
