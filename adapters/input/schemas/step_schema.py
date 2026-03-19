from uuid import UUID as StdUUID

from pydantic import Field, BaseModel

from arclith.adapters.input.schemas.base_schema import BaseSchema


class StepCreateSchema(BaseModel):
    name: str = Field(
        ...,
        description="Nom de l'ingrédient.",
        examples=["Farine de blé", "Sel fin"]
    )

    description: str | None = Field(
        None,
        description="La description détaillée de l'étape. None si non applicable.",
        examples=[
            "Mélanger la farine, l'eau et la levure pour préparer la pâte.",
            "Cuire la pizza au four à 220°C pendant 15 minutes.",
            None])


class StepPatchSchema(StepCreateSchema):
    name: str | None = Field(
        None,
        description="Nouveau nom de l'ingrédient. Ignoré si absent.",
        examples=["Farine complète", None]
    )


class StepUpdateSchema(StepCreateSchema):
    pass


class StepCreatedSchema(BaseModel):
    uuid: StdUUID = Field(
        description="Identifiant unique de l'ingrédient créé (UUIDv7).",
        examples=["01951234-5678-7abc-def0-123456789abc"],
    )


class StepSchema(BaseSchema):
    name: str = Field(
        ...,
        description="Nom de l'ingrédient.",
        examples=["Farine de blé", "Sel fin"]
    )

    description: str | None = Field(
        None,
        description="La description détaillée de l'étape. None si non applicable.",
        examples=[
            "Mélanger la farine, l'eau et la levure pour préparer la pâte.",
            "Cuire la pizza au four à 220°C pendant 15 minutes.",
            None])
