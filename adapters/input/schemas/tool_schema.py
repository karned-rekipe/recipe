from pydantic import BaseModel, Field
from typing import Optional

from arclith.adapters.input.schemas.base_schema import BaseSchema
from uuid import UUID as StdUUID

class ToolCreateSchema(BaseModel):
    name: str = Field(
        ...,
        description="Nom de l'outil.",
        examples=["Pizza maker", "Salad maker"]
    )


class ToolPatchSchema(ToolCreateSchema):
    pass


class ToolUpdateSchema(ToolCreateSchema):
    pass


class ToolCreatedSchema(BaseModel):
    uuid: StdUUID = Field(
        description="Identifiant unique de l'outil créé.",
        examples=["01951234-5678-7abc-def0-123456789abc"]
    )


class ToolSchema(BaseSchema):
    name: str = Field(
        ...,
        description="Nom de l'outil.",
        examples=["Pizza maker", "Salad maker"]
    )

