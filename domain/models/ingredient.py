from collections.abc import Iterable
from typing import Literal
from uuid import UUID as StdUUID

from pydantic import BaseModel, Field, field_validator

from arclith.domain.models.entity import Entity
from uuid6 import UUID

class MediaProfile(BaseModel):
    main_image_uri: str | None = None
    image_status: Literal["missing", "generated", "uploaded", "rejected"] = "missing"
    image_prompt: str | None = None
    source: Literal["manual", "ai", "import", "unknown"] = "unknown"
    validated: bool = False


class SeasonalityProfile(BaseModel):
    availability_type: Literal["unknown", "year_round", "seasonal", "not_applicable"] = "unknown"
    months: dict[int, int] = Field(default_factory=dict)
    geography: str | None = None
    source: Literal["manual", "dataset", "ai", "import", "legacy_hint", "unknown"] = "unknown"
    confidence: float | None = Field(default=None, ge=0, le=1)
    validated: bool = False

    @field_validator("months", mode="before")
    @classmethod
    def validate_months(cls, value: dict) -> dict[int, int]:
        for month, score in value.items():
            month_int = int(month)
            if not 1 <= month_int <= 12:
                raise ValueError(f"Month key must be between 1 and 12, got {month_int}")
            if not 1 <= int(score) <= 3:
                raise ValueError(f"Season score must be between 1 and 3, got {score}")
        return {int(key): int(score) for key, score in value.items()}


class NutritionProfile(BaseModel):
    kcal_per_100g: float | None = Field(default=None, ge=0)
    kcal_per_100ml: float | None = Field(default=None, ge=0)
    nutri_score: Literal["A", "B", "C", "D", "E", "not_applicable", "unknown"] = "unknown"
    ciqual_code: str | None = None
    source: Literal["manual", "ciqual", "openfoodfacts", "ai", "import", "unknown"] = "unknown"
    confidence: float | None = Field(default=None, ge=0, le=1)
    validated: bool = False


class SustainabilityProfile(BaseModel):
    carbon_kg_co2e_per_kg: float | None = Field(default=None, ge=0)
    agribalyse_code: str | None = None
    environmental_score: float | None = Field(default=None, ge=0)
    source: Literal["manual", "agribalyse", "openfoodfacts", "ai", "import", "unknown"] = "unknown"
    confidence: float | None = Field(default=None, ge=0, le=1)
    validated: bool = False


class IngredientAllergen(BaseModel):
    code: Literal[
        "gluten",
        "crustaceans",
        "eggs",
        "fish",
        "peanuts",
        "soy",
        "milk",
        "nuts",
        "celery",
        "mustard",
        "sesame",
        "sulphites",
        "lupin",
        "molluscs",
    ]
    presence: Literal["contains", "may_contain", "absent", "unknown"] = "unknown"
    note: str | None = None


class AllergenProfile(BaseModel):
    allergens: list[IngredientAllergen] = Field(default_factory=list)
    source: Literal["manual", "regulation", "openfoodfacts", "ai", "import", "unknown"] = "unknown"
    confidence: float | None = Field(default=None, ge=0, le=1)
    validated: bool = False


class UnitConversion(BaseModel):
    from_unit: str
    to_unit: str
    factor: float = Field(gt=0)
    source: Literal["global", "ingredient_specific", "package_profile"] = "ingredient_specific"
    confidence: float | None = Field(default=None, ge=0, le=1)


class UnitProfile(BaseModel):
    reference_unit: Literal["g", "kg", "ml", "cl", "l", "piece", "serving", "unknown"] = "unknown"
    default_purchase_unit: str | None = None
    default_recipe_unit: str | None = None
    allowed_units: list[str] = Field(default_factory=list)
    conversions: list[UnitConversion] = Field(default_factory=list)


class PackageProfile(BaseModel):
    label: str
    package_unit: Literal["paquet", "bouteille", "boite", "barquette", "piece", "custom"]
    net_quantity: float = Field(gt=0)
    net_unit: Literal["g", "ml", "piece"]
    servings_count: float | None = Field(default=None, gt=0)
    serving_label: str | None = None
    serving_quantity: float | None = Field(default=None, gt=0)
    serving_unit: Literal["g", "ml", "piece"] | None = None
    source: Literal["manual", "ai", "import", "supplier", "unknown"] = "unknown"
    validated: bool = False


class SubstitutionProfile(BaseModel):
    default_policy: Literal["unknown", "substitutable", "essential_by_default"] = "unknown"
    substitute_ingredient_uuids: list[StdUUID] = Field(default_factory=list)
    notes: str | None = None
    source: Literal["manual", "ai", "import", "unknown"] = "unknown"
    confidence: float | None = Field(default=None, ge=0, le=1)
    validated: bool = False

    @field_validator("substitute_ingredient_uuids", mode="before")
    @classmethod
    def coerce_substitute_uuids(cls, value: object) -> list[StdUUID]:
        if value is None:
            return []
        if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
            raise ValueError("substitute_ingredient_uuids must be a list")
        return [item if isinstance(item, StdUUID) else StdUUID(str(item)) for item in value]


class EnrichmentProfile(BaseModel):
    completeness_score: int = Field(default=0, ge=0, le=100)
    status: Literal["missing", "partial", "suggested", "validated", "rejected"] = "missing"
    missing_fields: list[str] = Field(default_factory=list)
    last_run_uuid: StdUUID | None = None
    last_enriched_at: str | None = None
    validated_fields: list[str] = Field(default_factory=list)
    rejected_fields: list[str] = Field(default_factory=list)

    @field_validator("last_run_uuid", mode="before")
    @classmethod
    def coerce_last_run_uuid(cls, value: object) -> StdUUID | None:
        if value is None or isinstance(value, StdUUID):
            return value
        return StdUUID(str(value))


class Ingredient(Entity):
    name: str = Field(
        ...,
        description="Ingredient name, normalized (leading/trailing spaces removed).",
        examples=["Tomate", "Farine de blé"],
    )
    rayon_uuid: UUID | None = Field(
        None,
        description="Referenced shelf/aisle UUID.",
        examples=["01951234-5678-7abc-def0-123456789abc"],
    )
    group_uuid: UUID | None = Field(
        None,
        description="Referenced food group UUID.",
        examples=["01951234-5678-7abc-def0-123456789abd"],
    )
    main_supplier_uuid: UUID | None = Field(
        None,
        description="Preferred supplier UUID owned by the shopping service.",
        examples=["01951234-5678-7abc-def0-123456789abe"],
    )
    secondary_supplier_uuids: list[UUID] = Field(
        default_factory=list,
        description="Other possible supplier UUIDs owned by the shopping service.",
        examples=[["01951234-5678-7abc-def0-123456789abf"]],
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
    def strip_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Ingredient name cannot be empty")
        return stripped

    @field_validator("rayon_uuid", "group_uuid", "main_supplier_uuid", mode="before")
    @classmethod
    def coerce_catalog_uuid(cls, value: object) -> UUID | None:
        if value is None or isinstance(value, UUID):
            return value
        return UUID(str(value))

    @field_validator("secondary_supplier_uuids", mode="before")
    @classmethod
    def coerce_secondary_supplier_uuids(cls, value: object) -> list[UUID]:
        if value is None:
            return []
        if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
            raise ValueError("secondary_supplier_uuids must be a list")
        return [item if isinstance(item, UUID) else UUID(str(item)) for item in value]

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
