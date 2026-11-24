from pydantic import BaseModel, ConfigDict, Field, field_validator
from uuid import UUID as StdUUID

from arclith.adapters.input.schemas.base_schema import BaseSchema
from adapters.input.schemas.ingredient_group_schema import IngredientGroupSchema
from adapters.input.schemas.ingredient_rayon_schema import IngredientRayonSchema
from domain.models.ingredient import (
    AllergenProfile,
    EnrichmentProfile,
    MediaProfile,
    NutritionProfile,
    PackageProfile,
    SeasonalityProfile,
    SubstitutionProfile,
    SustainabilityProfile,
    UnitProfile,
)
from domain.models.ingredient_image_generation import IngredientImageGeneration


class IngredientCreateSchema(BaseModel):
    name: str = Field(
        ...,
        description="Ingredient name.",
        examples=["Tomate", "Farine de blé"],
        min_length=1,
    )
    rayon_uuid: StdUUID | None = Field(None, description="Shelf/aisle UUID.")
    group_uuid: StdUUID | None = Field(None, description="Food group UUID.")
    main_supplier_uuid: StdUUID | None = Field(None, description="Preferred supplier UUID.")
    secondary_supplier_uuids: list[StdUUID] = Field(default_factory=list, description="Other possible supplier UUIDs.")
    green_score: int | None = Field(None, description="Environmental score (OpenFoodFacts scale).", ge=0, examples=[80])
    unit: str | None = Field(None, description="Unit of measure.", examples=["g", "ml", "pièce"])
    quantity: float | None = Field(None, description="Default quantity.", ge=0, examples=[100.0])
    season_months: dict[int, int] = Field(
        default_factory=dict,
        description="Legacy seasonality hint. Empty means unknown, not year-round.",
        examples=[{6: 2, 7: 3, 8: 3, 9: 2}],
    )
    media_profile: MediaProfile = Field(default_factory=MediaProfile)
    seasonality_profile: SeasonalityProfile = Field(default_factory=SeasonalityProfile)
    nutrition_profile: NutritionProfile = Field(default_factory=NutritionProfile)
    sustainability_profile: SustainabilityProfile = Field(default_factory=SustainabilityProfile)
    allergen_profile: AllergenProfile = Field(default_factory=AllergenProfile)
    unit_profile: UnitProfile = Field(default_factory=UnitProfile)
    package_profiles: list[PackageProfile] = Field(default_factory=list)
    substitution_profile: SubstitutionProfile = Field(default_factory=SubstitutionProfile)
    enrichment_profile: EnrichmentProfile = Field(default_factory=EnrichmentProfile)

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
    rayon_uuid: StdUUID | None = Field(None, description="Shelf/aisle UUID.")
    group_uuid: StdUUID | None = Field(None, description="Food group UUID.")
    main_supplier_uuid: StdUUID | None = Field(None, description="Preferred supplier UUID.")
    secondary_supplier_uuids: list[StdUUID] | None = Field(None, description="Other possible supplier UUIDs.")
    green_score: int | None = Field(None, description="Environmental score.", ge=0, examples=[60])
    unit: str | None = Field(None, description="Unit of measure.", examples=["kg"])
    quantity: float | None = Field(None, description="Default quantity.", ge=0, examples=[500.0])
    season_months: dict[int, int] | None = Field(None, description="Seasonality map.")
    media_profile: MediaProfile | None = None
    seasonality_profile: SeasonalityProfile | None = None
    nutrition_profile: NutritionProfile | None = None
    sustainability_profile: SustainabilityProfile | None = None
    allergen_profile: AllergenProfile | None = None
    unit_profile: UnitProfile | None = None
    package_profiles: list[PackageProfile] | None = None
    substitution_profile: SubstitutionProfile | None = None
    enrichment_profile: EnrichmentProfile | None = None

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


class UnitSchema(BaseModel):
    code: str
    label: str
    kind: str


class IngredientUnitConversionRequestSchema(BaseModel):
    quantity: float = Field(gt=0)
    from_unit: str = Field(min_length=1)
    to_unit: str = Field(min_length=1)


class IngredientUnitConversionResponseSchema(BaseModel):
    ingredient_uuid: StdUUID
    quantity: float
    from_unit: str
    converted_quantity: float
    to_unit: str
    factor: float
    source: str


class IngredientImageGenerationResponseSchema(IngredientImageGeneration):
    """Reviewable image suggestion created by the internal ingredient agent."""


class IngredientImageGenerationRequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IngredientSchema(BaseSchema):
    name: str = Field(..., description="Ingredient name.", examples=["Tomate"])
    rayon_uuid: StdUUID | None = Field(None, description="Shelf/aisle UUID.")
    group_uuid: StdUUID | None = Field(None, description="Food group UUID.")
    main_supplier_uuid: StdUUID | None = Field(None, description="Preferred supplier UUID.")
    secondary_supplier_uuids: list[StdUUID] = Field(default_factory=list, description="Other possible supplier UUIDs.")
    rayon: IngredientRayonSchema | None = Field(None, description="Hydrated shelf/aisle.")
    group: IngredientGroupSchema | None = Field(None, description="Hydrated food group.")
    green_score: int | None = Field(None, description="Environmental score.")
    unit: str | None = Field(None, description="Unit of measure.")
    quantity: float | None = Field(None, description="Default quantity.")
    season_months: dict[int, int] = Field(default_factory=dict, description="Seasonality map.")
    media_profile: MediaProfile = Field(default_factory=MediaProfile)
    suggested_media_profile: MediaProfile | None = Field(
        None,
        description="Latest unresolved image suggestion, exposed as a durable preview without applying it.",
    )
    seasonality_profile: SeasonalityProfile = Field(default_factory=SeasonalityProfile)
    nutrition_profile: NutritionProfile = Field(default_factory=NutritionProfile)
    sustainability_profile: SustainabilityProfile = Field(default_factory=SustainabilityProfile)
    allergen_profile: AllergenProfile = Field(default_factory=AllergenProfile)
    unit_profile: UnitProfile = Field(default_factory=UnitProfile)
    package_profiles: list[PackageProfile] = Field(default_factory=list)
    substitution_profile: SubstitutionProfile = Field(default_factory=SubstitutionProfile)
    enrichment_profile: EnrichmentProfile = Field(default_factory=EnrichmentProfile)
