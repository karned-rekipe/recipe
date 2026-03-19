from pydantic import BaseModel, Field
from typing import Optional

from arclith.adapters.input.schemas.base_schema import BaseSchema
from uuid import UUID as StdUUID


class UstensilCreateSchema(BaseModel):
    name: str = Field(
        ...,
        description="Nom de l'ustensil.",
        examples=["Fouet", "Spatule"]
    )


class UstensilPatchSchema(UstensilCreateSchema):
    pass


class UstensilUpdateSchema(UstensilCreateSchema):
    pass


class UstensilCreatedSchema(BaseModel):
    uuid: StdUUID = Field(
        description="Identifiant unique de l'ustensil créé.",
        examples=["01951234-5678-7abc-def0-123456789abc"]
    )


class UstensilSchema(BaseSchema):
    name: str = Field(
        ...,
        description="Nom de l'ustensil.",
        examples=["Fouet", "Spatule"]
    )
