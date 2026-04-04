from uuid import UUID as StdUUID

from pydantic import BaseModel, Field, field_validator

from arclith.adapters.input.schemas.base_schema import BaseSchema

from domain.models.country import Country
from domain.models.meal_category import MealCategory
from domain.models.recipe import MealType

from .source_schema import SourceSchema
from .step_schema import StepSchema


class RecipeCreateSchema(BaseModel):
    name: str = Field(
        ...,
        description="Nom de la recette.",
        examples=["Pizza margherita", "Tarte tatin"],
        min_length=1,
    )
    description: str | None = Field(None, description="Description détaillée de la recette.")
    origin_country: Country | None = Field(None, description="Pays d'origine (code ISO 3166-1 alpha-2).", examples=["FR", "IT"])
    meal_type: MealType | None = Field(None, description="Type de repas.", examples=["dinner", "lunch"])
    meal_category: MealCategory | None = Field(None, description="Catégorie du plat dans le repas.", examples=["first_course", "dessert"])
    servings: int | None = Field(None, description="Nombre de portions.", ge=1, examples=[4])
    unit_count: int | None = Field(None, description="Nombre d'unités.", ge=1, examples=[12])
    difficulty: int | None = Field(None, description="Niveau de difficulté de 1 à 5.", ge=1, le=5, examples=[3])
    price: int | None = Field(None, description="Niveau de prix de 1 à 5.", ge=1, le=5, examples=[2])
    main_image: str | None = Field(None, description="URI de l'image principale.")
    secondary_images: list[str] = Field(default_factory=list, description="URIs des images secondaires.")
    sources: list[SourceSchema] = Field(
        default_factory=list,
        description="Liste des sources de la recette.",
        examples=[[{"name": "Marmiton", "description": "Recette originale", "uri": "https://www.marmiton.org/recettes/recette_pizza.html"}]],
    )

    @field_validator("name", mode="before")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if isinstance(v, str) and not v.strip():
            raise ValueError("Name cannot be empty")
        return v


class RecipeUpdateSchema(RecipeCreateSchema):
    pass


class RecipePatchSchema(BaseModel):
    name: str | None = Field(None, description="Nouveau nom. Ignoré si absent.", min_length=1)
    description: str | None = None
    origin_country: Country | None = None
    meal_type: MealType | None = None
    meal_category: MealCategory | None = None
    servings: int | None = Field(None, ge=1)
    unit_count: int | None = Field(None, ge=1)
    difficulty: int | None = Field(None, ge=1, le=5)
    price: int | None = Field(None, ge=1, le=5)
    main_image: str | None = None
    secondary_images: list[str] | None = None
    sources: list[SourceSchema] | None = Field(
        None,
        examples=[[{"name": "Marmiton", "description": "Recette originale", "uri": "https://www.marmiton.org/recettes/recette_pizza.html"}]],
    )

    @field_validator("name", mode="before")
    @classmethod
    def name_not_empty(cls, v: str | None) -> str | None:
        if isinstance(v, str) and not v.strip():
            raise ValueError("Name cannot be empty")
        return v


class RecipeCreatedSchema(BaseModel):
    uuid: StdUUID = Field(
        description="Identifiant unique de la recette créée (UUIDv7).",
        examples=["01951234-5678-7abc-def0-123456789abc"],
    )


class RecipeSchema(BaseSchema):
    name: str = Field(..., description="Nom de la recette.", examples=["Pizza margherita"])
    description: str | None = None
    origin_country: Country | None = None
    meal_type: MealType | None = None
    meal_category: MealCategory | None = None
    servings: int | None = None
    unit_count: int | None = None
    difficulty: int | None = None
    price: int | None = None
    main_image: str | None = None
    secondary_images: list[str] = []
    sources: list[SourceSchema] = Field(
        default_factory=list,
        description="Liste des sources de la recette.",
        examples=[[{"name": "Marmiton", "description": "Recette originale", "uri": "https://www.marmiton.org/recettes/recette_pizza.html"}]],
    )
    steps: list[StepSchema] = Field(
        default_factory=list,
        description="Étapes ordonnées de la recette.",
        examples=[[{
            "uuid": "01951234-0001-7abc-def0-000000000001",
            "created_at": "2026-03-17T10:00:00+00:00",
            "updated_at": "2026-03-17T10:00:00+00:00",
            "created_by": None,
            "updated_by": None,
            "deleted_at": None,
            "deleted_by": None,
            "is_deleted": False,
            "version": 1,
            "name": "Préparer la pâte",
            "description": "Mélanger farine, eau, levure et sel.",
            "cooking_time": None,
            "rest_time": 60,
            "preparation_time": 15,
            "main_image": None,
            "secondary_images": [],
            "rank": 1,
            "total_time": 75,
        }]],
    )
