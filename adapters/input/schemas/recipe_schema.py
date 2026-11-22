from datetime import datetime
from typing import Any, Self
from uuid import UUID as StdUUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from arclith.adapters.input.schemas.base_schema import BaseSchema
from domain.models.country import Country
from domain.models.generated_recipe_image import GeneratedRecipeImage
from domain.models.meal_category import MealCategory
from domain.models.recipe import MealType, Recipe, RecipeQualityStatus, RecipeStatus, Source
from domain.models.recipe_component import RecipeComponent
from domain.models.recipe_equipment import RecipeEquipment
from domain.models.recipe_ingredient import RecipeIngredient
from domain.models.recipe_line_origin import RecipeLineOrigin
from domain.models.step import Step
from uuid6 import UUID

from .ingredient_group_schema import IngredientGroupSchema
from .ingredient_rayon_schema import IngredientRayonSchema
from .source_schema import SourceSchema
from .step_schema import StepSchema
from .tag_schema import TagSchema


class RecipeIngredientWriteSchema(BaseModel):
    ingredient_uuid: StdUUID = Field(
        ...,
        description="UUID of the ingredient catalog item.",
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
        min_length=1,
        examples=["g", "ml", "piece"],
    )
    component_uuid: StdUUID | None = Field(None, description="Projected component UUID, ignored for manual writes.")
    source_recipe_uuid: StdUUID | None = Field(None, description="Projected source recipe UUID, ignored for manual writes.")
    line_origin: RecipeLineOrigin = Field(RecipeLineOrigin.manual, description="Manual or projected line origin.")

    @field_validator("unit", mode="before")
    @classmethod
    def unit_not_empty(cls, v: str) -> str:
        if isinstance(v, str) and not v.strip():
            raise ValueError("Unit cannot be empty")
        return v


class RecipeIngredientSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ingredient_uuid: StdUUID = Field(
        ...,
        description="UUID of the ingredient catalog item.",
        examples=["01951234-5678-7abc-def0-123456789abc"],
    )
    name: str = Field(..., description="Ingredient name.", examples=["Tomate"])
    quantity: float = Field(..., description="Quantity required for the recipe.")
    unit: str = Field(..., description="Unit of measure.")
    season_months: dict[int, int] = Field(default_factory=dict, description="Seasonality map.")
    rayon_uuid: StdUUID | None = Field(None, description="Shelf/aisle UUID.")
    group_uuid: StdUUID | None = Field(None, description="Food group UUID.")
    main_supplier_uuid: StdUUID | None = Field(None, description="Preferred supplier UUID.")
    secondary_supplier_uuids: list[StdUUID] = Field(default_factory=list, description="Other possible supplier UUIDs.")
    rayon: IngredientRayonSchema | None = Field(None, description="Hydrated shelf/aisle.")
    group: IngredientGroupSchema | None = Field(None, description="Hydrated food group.")
    green_score: int | None = Field(None, description="Environmental score.")
    component_uuid: StdUUID | None = Field(None, description="Projected component UUID.")
    source_recipe_uuid: StdUUID | None = Field(None, description="Projected source recipe UUID.")
    line_origin: RecipeLineOrigin = Field(RecipeLineOrigin.manual, description="Manual or projected line origin.")


class RecipeComponentWriteSchema(BaseModel):
    uuid: StdUUID | None = Field(None, description="Stable embedded component UUID.")
    recipe_uuid: StdUUID = Field(..., description="Referenced child recipe UUID.")
    label: str = Field(..., min_length=1, description="Display label for the child recipe.")
    rank: int = Field(..., ge=1, description="Display order in the parent recipe.")
    servings_multiplier: float = Field(1.0, gt=0, description="Quantity multiplier applied to projected child lines.")

    @field_validator("label", mode="before")
    @classmethod
    def label_not_empty(cls, v: str) -> str:
        if isinstance(v, str) and not v.strip():
            raise ValueError("Label cannot be empty")
        return v


class RecipeComponentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: StdUUID = Field(..., description="Stable embedded component UUID.")
    recipe_uuid: StdUUID = Field(..., description="Referenced child recipe UUID.")
    label: str = Field(..., description="Display label for the child recipe.")
    rank: int = Field(..., ge=1, description="Display order in the parent recipe.")
    servings_multiplier: float = Field(..., gt=0, description="Quantity multiplier applied to projected child lines.")
    recipe_name: str | None = Field(None, description="Hydrated child recipe name.")
    ingredients: list[RecipeIngredientSchema] = Field(default_factory=list, description="Projected child ingredients.")
    steps: list[StepSchema] = Field(default_factory=list, description="Projected child steps.")


class RecipeEquipmentWriteSchema(BaseModel):
    equipment_uuid: StdUUID = Field(
        ...,
        description="UUID of the equipment catalog item.",
        examples=["01951234-5678-7abc-def0-123456789abc"],
    )
    quantity: float | None = Field(
        1,
        description="Optional quantity of required equipment.",
        ge=0,
        examples=[1.0, 2.0],
    )


class RecipeEquipmentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    equipment_uuid: StdUUID = Field(
        ...,
        description="UUID of the equipment catalog item.",
        examples=["01951234-5678-7abc-def0-123456789abc"],
    )
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
    component_uuid: StdUUID | None = Field(None, description="Projected component UUID, ignored for manual writes.")
    source_recipe_uuid: StdUUID | None = Field(None, description="Projected source recipe UUID, ignored for manual writes.")
    line_origin: RecipeLineOrigin = Field(RecipeLineOrigin.manual, description="Manual or projected line origin.")

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
    tag_uuids: list[StdUUID] = Field(default_factory=list, description="Liste des UUID de tags.")
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
    components: list[RecipeComponentWriteSchema] = Field(
        default_factory=list,
        description="Sous-recettes liees qui composent cette recette.",
    )
    ingredients: list[RecipeIngredientWriteSchema] = Field(
        default_factory=list,
        description="Liste des references ingredients de la recette.",
    )
    equipment: list[RecipeEquipmentWriteSchema] = Field(
        default_factory=list,
        description="Liste des references equipements necessaires.",
    )
    steps: list[RecipeStepWriteSchema] = Field(
        default_factory=list,
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
    tag_uuids: list[StdUUID] | None = None
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
    components: list[RecipeComponentWriteSchema] | None = None
    ingredients: list[RecipeIngredientWriteSchema] | None = None
    equipment: list[RecipeEquipmentWriteSchema] | None = None
    steps: list[RecipeStepWriteSchema] | None = None


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
            "tag_uuids": self.tag_uuids,
            "status": self.status,
            "quality_status": self.quality_status,
            "migration_metadata": self.migration_metadata,
            "components": self.components,
        }
        for field_name, value in non_nullable_when_present.items():
            if field_name in self.model_fields_set and value is None:
                raise ValueError(f"{field_name} cannot be null when provided")
        return self


class RecipeImageGenerationRequestSchema(BaseModel):
    prompt: str | None = Field(
        None,
        max_length=4000,
        description="Prompt optionnel. Media en construit un depuis la recette s'il est absent.",
    )
    replace_existing: bool = Field(
        False,
        description="Autorise le remplacement d'une image principale existante.",
    )


class RecipeAIEnrichmentRequestSchema(BaseModel):
    generate_image: bool = Field(
        True,
        description="Génère une image principale si la recette n'en possède pas.",
    )


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
    tag_uuids: list[StdUUID] = Field(default_factory=list)
    tags: list[TagSchema] = Field(default_factory=list)
    season_months: dict[int, int] = Field(default_factory=dict)
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
    components: list[RecipeComponentSchema] = Field(
        default_factory=list,
        description="Sous-recettes hydratees.",
    )
    ingredients: list[RecipeIngredientSchema] = Field(
        default_factory=list,
        description="Liste hydratee des ingredients.",
    )
    equipment: list[RecipeEquipmentSchema] = Field(
        default_factory=list,
        description="Liste hydratee des equipements.",
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


class RecipeImageGenerationResponseSchema(GeneratedRecipeImage):
    recipe: RecipeSchema


class RecipeAIEnrichmentResponseSchema(BaseModel):
    recipe: RecipeSchema
    recipe_uuid: str
    recipe_name: str
    formatted_response: str
    updated: bool
    image_generated: bool
    warnings: list[str] = Field(default_factory=list)


def recipe_create_payload_to_domain(payload: RecipeCreateSchema) -> Recipe:
    ingredients = [_to_recipe_ingredient(ingredient) for ingredient in payload.ingredients]
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
        tag_uuids=[UUID(str(tag_uuid)) for tag_uuid in payload.tag_uuids],
        status=_resolve_recipe_status(payload.status, payload.model_fields_set, ingredients),
        quality_status=payload.quality_status,
        legacy_id=payload.legacy_id,
        created_at_legacy=payload.created_at_legacy,
        updated_at_legacy=payload.updated_at_legacy,
        migration_metadata=dict(payload.migration_metadata),
        sources=[Source(**source.model_dump()) for source in payload.sources],
        components=[_to_recipe_component(component) for component in payload.components],
        ingredients=ingredients,
        equipment=[_to_recipe_equipment(item) for item in payload.equipment],
        steps=[_to_step(step) for step in payload.steps],
    )


def recipe_update_payload_to_domain(existing: Recipe, payload: RecipeUpdateSchema) -> Recipe:
    data = _recipe_model_data(existing)
    updates = _converted_recipe_values(payload.model_dump())
    _preserve_unspecified_update_values(updates, payload.model_fields_set)
    data.update(updates)
    data["season_months"] = dict(existing.season_months)
    data["status"] = _resolve_recipe_status(payload.status, payload.model_fields_set, data["ingredients"])
    return Recipe.model_validate(data)


def recipe_patch_payload_to_domain(existing: Recipe, payload: RecipePatchSchema) -> Recipe:
    data = _recipe_model_data(existing)
    data.update(_converted_recipe_values(payload.model_dump(exclude_unset=True)))
    data["status"] = _resolve_recipe_status(payload.status, payload.model_fields_set, data["ingredients"])
    return Recipe.model_validate(data)


def _recipe_model_data(recipe: Recipe) -> dict[str, Any]:
    return recipe.model_dump(mode="python", exclude_computed_fields=True)


def _converted_recipe_values(values: dict[str, Any]) -> dict[str, Any]:
    result = dict(values)
    _convert_tag_uuids(result)
    _convert_sources(result)
    _convert_components(result)
    _convert_ingredients(result)
    _convert_equipment(result)
    _convert_steps(result)
    return result


def _convert_tag_uuids(values: dict[str, Any]) -> None:
    if "tag_uuids" in values:
        values["tag_uuids"] = [UUID(str(tag_uuid)) for tag_uuid in values["tag_uuids"]]


def _convert_sources(values: dict[str, Any]) -> None:
    if "sources" in values:
        values["sources"] = [Source(**source) for source in values["sources"]]


def _convert_components(values: dict[str, Any]) -> None:
    if "components" in values:
        values["components"] = [RecipeComponent(**component) for component in values["components"]]


def _convert_ingredients(values: dict[str, Any]) -> None:
    if "ingredients" in values:
        values["ingredients"] = [RecipeIngredient(**ingredient) for ingredient in values["ingredients"]]


def _convert_equipment(values: dict[str, Any]) -> None:
    if "equipment" in values:
        values["equipment"] = [RecipeEquipment(**item) for item in values["equipment"]]


def _convert_steps(values: dict[str, Any]) -> None:
    if "steps" in values:
        values["steps"] = [Step(**step) for step in values["steps"]]


def _preserve_unspecified_update_values(updates: dict[str, Any], fields_set: set[str]) -> None:
    for field_name in (
        "favorite",
        "quality_status",
        "legacy_id",
        "created_at_legacy",
        "updated_at_legacy",
        "migration_metadata",
    ):
        if field_name not in fields_set:
            updates.pop(field_name, None)


def _to_recipe_ingredient(payload: RecipeIngredientWriteSchema) -> RecipeIngredient:
    return RecipeIngredient(
        ingredient_uuid=UUID(str(payload.ingredient_uuid)),
        quantity=payload.quantity,
        unit=payload.unit,
        component_uuid=UUID(str(payload.component_uuid)) if payload.component_uuid is not None else None,
        source_recipe_uuid=UUID(str(payload.source_recipe_uuid)) if payload.source_recipe_uuid is not None else None,
        line_origin=payload.line_origin,
    )


def _to_recipe_component(payload: RecipeComponentWriteSchema) -> RecipeComponent:
    data = payload.model_dump(exclude_none=True)
    return RecipeComponent(**data)


def _to_recipe_equipment(payload: RecipeEquipmentWriteSchema) -> RecipeEquipment:
    return RecipeEquipment(
        equipment_uuid=UUID(str(payload.equipment_uuid)),
        quantity=payload.quantity,
    )


def _to_step(payload: RecipeStepWriteSchema) -> Step:
    return Step(**payload.model_dump())


def _resolve_recipe_status(
    payload_status: RecipeStatus | None,
    fields_set: set[str],
    ingredients: list[RecipeIngredient],
) -> RecipeStatus:
    if "status" in fields_set and payload_status == RecipeStatus.archived:
        return RecipeStatus.archived
    return RecipeStatus.active if ingredients else RecipeStatus.draft
