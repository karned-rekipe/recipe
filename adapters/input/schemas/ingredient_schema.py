from uuid import UUID as StdUUID

from pydantic import Field, BaseModel

from arclith.adapters.input.schemas.base_schema import BaseSchema


class IngredientCreateSchema(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        description="Nom de l'ingrédient.",
        examples=["Farine de blé", "Sel fin"]
    )

    unit: str | None = Field(
        None,
        min_length=1,
        description="Unité de mesure (ex. g, kg, ml). None si non applicable.",
        examples=["g", "kg", "ml", None]
    )


class IngredientPatchSchema(IngredientCreateSchema):
    name: str | None = Field(
        None,
        min_length=1,
        description="Nouveau nom de l'ingrédient. Ignoré si absent.",
        examples=["Farine complète", None]
    )


class IngredientUpdateSchema(IngredientCreateSchema):
    pass


class IngredientCreatedSchema(BaseModel):
    uuid: StdUUID = Field(
        description="Identifiant unique de l'ingrédient créé (UUIDv7).",
        examples=["01951234-5678-7abc-def0-123456789abc"],
    )


class IngredientSchema(BaseSchema):
    name: str = Field(
        ...,
        min_length=1,
        description="Nom de l'ingrédient.",
        examples=["Farine de blé", "Sel fin"]
    )

    unit: str | None = Field(
        None,
        min_length=1,
        description="Unité de mesure (ex. g, kg, ml). None si non applicable.",
        examples=["g", "kg", "ml", None]
    )
