from uuid import UUID as StdUUID

from pydantic import BaseModel, Field, field_validator

from arclith.adapters.input.schemas.base_schema import BaseSchema


class EquipmentCreateSchema(BaseModel):
    name: str = Field(
        ...,
        description="Equipment name.",
        examples=["Four", "Saladier"],
        min_length=1,
    )
    description: str | None = Field(None, description="Optional equipment details.")

    @field_validator("name", mode="before")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if isinstance(v, str) and not v.strip():
            raise ValueError("Name cannot be empty")
        return v


class EquipmentPatchSchema(BaseModel):
    name: str | None = Field(None, description="New equipment name.", min_length=1)
    description: str | None = Field(None, description="Optional equipment details.")

    @field_validator("name", mode="before")
    @classmethod
    def name_not_empty(cls, v: str | None) -> str | None:
        if isinstance(v, str) and not v.strip():
            raise ValueError("Name cannot be empty")
        return v


class EquipmentUpdateSchema(EquipmentCreateSchema):
    pass


class EquipmentCreatedSchema(BaseModel):
    uuid: StdUUID = Field(
        description="Unique identifier of the created equipment (UUIDv7).",
        examples=["01951234-5678-7abc-def0-123456789abc"],
    )


class EquipmentSchema(BaseSchema):
    name: str = Field(..., description="Equipment name.", examples=["Four"])
    description: str | None = Field(None, description="Optional equipment details.")
