from datetime import datetime
from typing import Self
from uuid import UUID as StdUUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from arclith.adapters.input.schemas.base_schema import BaseSchema
from domain.models.country import Country
from domain.models.meal_category import MealCategory
from domain.models.recipe import MealType, Recipe, RecipeQualityStatus, RecipeStatus, Source
from domain.models.recipe_equipment import RecipeEquipment
from domain.models.recipe_ingredient import RecipeIngredient
from domain.models.step import Step

from .ingredient_schema import IngredientCreateSchema
from .source_schema import SourceSchema
from .step_schema import StepSchema


class RecipeIngredientWriteSchema(IngredientCreateSchema):
    quantity: float = Field(
        ...,
        description="Quantity required for the recipe.",
        gt=0,
        examples=[100.0, 1.0],
    )
    unit: str = Field(
        ...,
        description="Unit of measure for the recipe quantity.",
        min_length=1,
        examples=["g", "ml", "piece"],
    )

    @field_validator("unit", mode="before")
    @classmethod
    def unit_not_empty(cls, v: str) -> str:
        if isinstance(v, str) and not v.strip():
            raise ValueError("Unit cannot be empty")
        return v


class RecipeIngredientSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Ingredient name.", examples=["Tomate"])
    quantity: float = Field(..., description="Quantity required for the recipe.")
    unit: str = Field(..., description="Unit of measure.")
    season_months: dict[int, int] = Field(default_factory=dict, description="Seasonality map.")
    rayon: str | None = Field(None, description="Shelf/aisle category.")
    group: str | None = Field(None, description="Food group.")
    green_score: int | None = Field(None, description="Environmental score.")


class RecipeEquipmentWriteSchema(BaseModel):
    name: str = Field(
        ...,
        description="Equipment name.",
        min_length=1,
        examples=["Four", "Saladier"],
    )
    quantity: float | None = Field(
        None,
        description="Optional quantity of required equipment.",
        ge=0,
        examples=[1.0, 2.0],
    )

    @field_validator("name", mode="before")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if isinstance(v, str) and not v.strip():
            raise ValueError("Name cannot be empty")
        return v


class RecipeEquipmentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Equipment name.", examples=["Four"])
    quantity: float | None = Field(None, description="Optional quantity of required equipment.")


class RecipeStepWriteSchema(BaseModel):
    name: str = Field(
        ...,
        description="Step title.",
        min_length=1,
        examples=["Preparer la pate", "Cuire au four"],
    )
    description: str | None = Field(None, description="Detailed description of the step.")
    cooking_time: int | None = Field(None, description="Cooking time in minutes.", ge=0, examples=[25])
    rest_time: int | None = Field(None, description="Rest time in minutes.", ge=0, examples=[60])
    preparation_time: int | None = Field(None, description="Preparation time in minutes.", ge=0, examples=[15])
    main_image: str | None = Field(None, description="URI of the main image for the step.")
    secondary_images: list[str] = Field(default_factory=list, description="URIs of secondary step images.")
    rank: int = Field(..., description="Order of the step in the recipe.", ge=1, examples=[1, 2, 3])

    @field_validator("name", mode="before")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if isinstance(v, str) and not v.strip():
            raise ValueError("Name cannot be empty")
        return v


class RecipeCreateSchema(BaseModel):
    name: str = Field(
        ...,
        description="Nom de la recette.",
        examples=["Pizza margherita", "Tarte tatin"],
        min_length=1,
    )
    description: str | None = Field(None, description="Description detaillee de la recette.")
    origin_country: Country | None = Field(
        None,
        description="Pays d'origine (code ISO 3166-1 alpha-2).",
        examples=["FR", "IT"],
    )
    meal_type: MealType | None = Field(None, description="Type de repas.", examples=["dinner", "lunch"])
    meal_category: MealCategory | None = Field(
        None,
        description="Categorie du plat dans le repas.",
        examples=["first_course", "dessert"],
    )
    servings: int = Field(..., description="Nombre de portions.", ge=1, examples=[4])
    unit_count: int | None = Field(None, description="Nombre d'unites.", ge=1, examples=[12])
    difficulty: int | None = Field(None, description="Niveau de difficulte de 1 a 5.", ge=1, le=5, examples=[3])
    price: int | None = Field(None, description="Niveau de prix de 1 a 5.", ge=1, le=5, examples=[2])
    main_image: str | None = Field(None, description="URI de l'image principale.")
    secondary_images: list[str] = Field(default_factory=list, description="URIs des images secondaires.")
    favorite: bool = Field(False, description="Indique si la recette est favorite.")
    status: RecipeStatus = Field(RecipeStatus.active, description="Statut de cycle de vie de la recette.")
    quality_status: RecipeQualityStatus = Field(
        RecipeQualityStatus.structured,
        description="Statut de completude/qualite pour migration et enrichissement progressif.",
    )
    legacy_id: int | None = Field(None, description="Identifiant stable de la recette legacy.", ge=1)
    created_at_legacy: datetime | None = Field(None, description="Date de creation issue du legacy.")
    updated_at_legacy: datetime | None = Field(None, description="Date de derniere modification issue du legacy.")
    migration_metadata: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description="Metadonnees techniques de migration/import.",
    )
    sources: list[SourceSchema] = Field(
        default_factory=list,
        description="Liste des sources de la recette.",
        examples=[[{"name": "Marmiton", "description": "Recette originale", "uri": "https://www.marmiton.org/recettes/recette_pizza.html"}]],
    )
    ingredients: list[RecipeIngredientWriteSchema] = Field(
        ...,
        min_length=1,
        description="Liste embarquee des ingredients de la recette.",
    )
    equipment: list[RecipeEquipmentWriteSchema] = Field(
        default_factory=list,
        description="Liste embarquee des equipements necessaires.",
    )
    steps: list[RecipeStepWriteSchema] = Field(
        ...,
        min_length=1,
        description="Liste ordonnee des etapes de la recette.",
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
    name: str | None = Field(None, description="Nouveau nom. Ignore si absent.", min_length=1)
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
    favorite: bool | None = None
    status: RecipeStatus | None = None
    quality_status: RecipeQualityStatus | None = None
    legacy_id: int | None = Field(None, ge=1)
    created_at_legacy: datetime | None = None
    updated_at_legacy: datetime | None = None
    migration_metadata: dict[str, str | int | float | bool | None] | None = None
    sources: list[SourceSchema] | None = Field(
        None,
        examples=[[{"name": "Marmiton", "description": "Recette originale", "uri": "https://www.marmiton.org/recettes/recette_pizza.html"}]],
    )
    ingredients: list[RecipeIngredientWriteSchema] | None = Field(None, min_length=1)
    equipment: list[RecipeEquipmentWriteSchema] | None = None
    steps: list[RecipeStepWriteSchema] | None = Field(None, min_length=1)

    @field_validator("name", mode="before")
    @classmethod
    def name_not_empty(cls, v: str | None) -> str | None:
        if isinstance(v, str) and not v.strip():
            raise ValueError("Name cannot be empty")
        return v

    @model_validator(mode="after")
    def reject_invalid_null_replacements(self) -> Self:
        non_nullable_when_present = {
            "name": self.name,
            "servings": self.servings,
            "ingredients": self.ingredients,
            "steps": self.steps,
            "equipment": self.equipment,
            "secondary_images": self.secondary_images,
            "sources": self.sources,
            "favorite": self.favorite,
            "status": self.status,
            "quality_status": self.quality_status,
            "migration_metadata": self.migration_metadata,
        }
        for field_name, value in non_nullable_when_present.items():
            if field_name in self.model_fields_set and value is None:
                raise ValueError(f"{field_name} cannot be null when provided")
        return self


class RecipeCreatedSchema(BaseModel):
    uuid: StdUUID = Field(
        description="Identifiant unique de la recette creee (UUIDv7).",
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
    secondary_images: list[str] = Field(default_factory=list)
    favorite: bool = False
    status: RecipeStatus = RecipeStatus.active
    quality_status: RecipeQualityStatus = RecipeQualityStatus.structured
    legacy_id: int | None = None
    created_at_legacy: datetime | None = None
    updated_at_legacy: datetime | None = None
    migration_metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    sources: list[SourceSchema] = Field(
        default_factory=list,
        description="Liste des sources de la recette.",
        examples=[[{"name": "Marmiton", "description": "Recette originale", "uri": "https://www.marmiton.org/recettes/recette_pizza.html"}]],
    )
    ingredients: list[RecipeIngredientSchema] = Field(
        default_factory=list,
        description="Liste embarquee des ingredients.",
    )
    equipment: list[RecipeEquipmentSchema] = Field(
        default_factory=list,
        description="Liste embarquee des equipements.",
    )
    steps: list[StepSchema] = Field(
        default_factory=list,
        description="Etapes ordonnees de la recette.",
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
            "name": "Preparer la pate",
            "description": "Melanger farine, eau, levure et sel.",
            "cooking_time": None,
            "rest_time": 60,
            "preparation_time": 15,
            "main_image": None,
            "secondary_images": [],
            "rank": 1,
            "total_time": 75,
        }]],
    )


def recipe_create_payload_to_domain(payload: RecipeCreateSchema) -> Recipe:
    return Recipe(
        name=payload.name,
        description=payload.description,
        origin_country=payload.origin_country,
        meal_type=payload.meal_type,
        meal_category=payload.meal_category,
        servings=payload.servings,
        unit_count=payload.unit_count,
        difficulty=payload.difficulty,
        price=payload.price,
        main_image=payload.main_image,
        secondary_images=list(payload.secondary_images),
        favorite=payload.favorite,
        status=payload.status,
        quality_status=payload.quality_status,
        legacy_id=payload.legacy_id,
        created_at_legacy=payload.created_at_legacy,
        updated_at_legacy=payload.updated_at_legacy,
        migration_metadata=dict(payload.migration_metadata),
        sources=[Source(**source.model_dump()) for source in payload.sources],
        ingredients=[_to_recipe_ingredient(ingredient) for ingredient in payload.ingredients],
        equipment=[_to_recipe_equipment(item) for item in payload.equipment],
        steps=[_to_step(step) for step in payload.steps],
    )


def recipe_update_payload_to_domain(existing: Recipe, payload: RecipeUpdateSchema) -> Recipe:
    return Recipe(
        uuid=existing.uuid,
        created_at=existing.created_at,
        created_by=existing.created_by,
        updated_at=existing.updated_at,
        updated_by=existing.updated_by,
        deleted_at=existing.deleted_at,
        deleted_by=existing.deleted_by,
        version=existing.version,
        name=payload.name,
        description=payload.description,
        origin_country=payload.origin_country,
        meal_type=payload.meal_type,
        meal_category=payload.meal_category,
        servings=payload.servings,
        unit_count=payload.unit_count,
        difficulty=payload.difficulty,
        price=payload.price,
        main_image=payload.main_image,
        secondary_images=list(payload.secondary_images),
        favorite=payload.favorite if "favorite" in payload.model_fields_set else existing.favorite,
        status=payload.status if "status" in payload.model_fields_set else existing.status,
        quality_status=payload.quality_status if "quality_status" in payload.model_fields_set else existing.quality_status,
        legacy_id=payload.legacy_id if "legacy_id" in payload.model_fields_set else existing.legacy_id,
        created_at_legacy=payload.created_at_legacy if "created_at_legacy" in payload.model_fields_set else existing.created_at_legacy,
        updated_at_legacy=payload.updated_at_legacy if "updated_at_legacy" in payload.model_fields_set else existing.updated_at_legacy,
        migration_metadata=dict(payload.migration_metadata)
        if "migration_metadata" in payload.model_fields_set
        else dict(existing.migration_metadata),
        sources=[Source(**source.model_dump()) for source in payload.sources],
        ingredients=[_to_recipe_ingredient(ingredient) for ingredient in payload.ingredients],
        equipment=[_to_recipe_equipment(item) for item in payload.equipment],
        steps=[_to_step(step) for step in payload.steps],
    )


def recipe_patch_payload_to_domain(existing: Recipe, payload: RecipePatchSchema) -> Recipe:
    fields_set = payload.model_fields_set

    secondary_images = list(existing.secondary_images)
    if "secondary_images" in fields_set:
        if payload.secondary_images is None:
            raise ValueError("secondary_images cannot be null when provided")
        secondary_images = list(payload.secondary_images)

    migration_metadata = dict(existing.migration_metadata)
    if "migration_metadata" in fields_set:
        if payload.migration_metadata is None:
            raise ValueError("migration_metadata cannot be null when provided")
        migration_metadata = dict(payload.migration_metadata)

    sources = list(existing.sources)
    if "sources" in fields_set:
        if payload.sources is None:
            raise ValueError("sources cannot be null when provided")
        sources = [Source(**source.model_dump()) for source in payload.sources]

    ingredients = list(existing.ingredients)
    if "ingredients" in fields_set:
        if payload.ingredients is None:
            raise ValueError("ingredients cannot be null when provided")
        ingredients = [_to_recipe_ingredient(ingredient) for ingredient in payload.ingredients]

    equipment = list(existing.equipment)
    if "equipment" in fields_set:
        if payload.equipment is None:
            raise ValueError("equipment cannot be null when provided")
        equipment = [_to_recipe_equipment(item) for item in payload.equipment]

    steps = list(existing.steps)
    if "steps" in fields_set:
        if payload.steps is None:
            raise ValueError("steps cannot be null when provided")
        steps = [_to_step(step) for step in payload.steps]

    return Recipe(
        uuid=existing.uuid,
        created_at=existing.created_at,
        created_by=existing.created_by,
        updated_at=existing.updated_at,
        updated_by=existing.updated_by,
        deleted_at=existing.deleted_at,
        deleted_by=existing.deleted_by,
        version=existing.version,
        name=payload.name if "name" in fields_set else existing.name,
        description=payload.description if "description" in fields_set else existing.description,
        origin_country=payload.origin_country if "origin_country" in fields_set else existing.origin_country,
        meal_type=payload.meal_type if "meal_type" in fields_set else existing.meal_type,
        meal_category=payload.meal_category if "meal_category" in fields_set else existing.meal_category,
        servings=payload.servings if "servings" in fields_set else existing.servings,
        unit_count=payload.unit_count if "unit_count" in fields_set else existing.unit_count,
        difficulty=payload.difficulty if "difficulty" in fields_set else existing.difficulty,
        price=payload.price if "price" in fields_set else existing.price,
        main_image=payload.main_image if "main_image" in fields_set else existing.main_image,
        secondary_images=secondary_images,
        favorite=payload.favorite if "favorite" in fields_set else existing.favorite,
        status=payload.status if "status" in fields_set else existing.status,
        quality_status=payload.quality_status if "quality_status" in fields_set else existing.quality_status,
        legacy_id=payload.legacy_id if "legacy_id" in fields_set else existing.legacy_id,
        created_at_legacy=payload.created_at_legacy if "created_at_legacy" in fields_set else existing.created_at_legacy,
        updated_at_legacy=payload.updated_at_legacy if "updated_at_legacy" in fields_set else existing.updated_at_legacy,
        migration_metadata=migration_metadata,
        sources=sources,
        ingredients=ingredients,
        equipment=equipment,
        steps=steps,
    )


def _to_recipe_ingredient(payload: RecipeIngredientWriteSchema) -> RecipeIngredient:
    return RecipeIngredient(**payload.model_dump())


def _to_recipe_equipment(payload: RecipeEquipmentWriteSchema) -> RecipeEquipment:
    return RecipeEquipment(**payload.model_dump())


def _to_step(payload: RecipeStepWriteSchema) -> Step:
    return Step(**payload.model_dump())
