from pydantic import BaseModel, Field, field_validator
from uuid import UUID


class RecipeEquipment(BaseModel):
    equipment_uuid: UUID = Field(
        ...,
        description="Reference to the equipment catalog item.",
        examples=["01951234-5678-7abc-def0-123456789abc"],
    )
    quantity: float | None = Field(
        1,
        description="Optional quantity of required equipment.",
        ge=0,
        examples=[1.0, 2.0],
    )

    @field_validator("equipment_uuid", mode="before")
    @classmethod
    def coerce_uuid(cls, v: object) -> UUID:
        if isinstance(v, UUID):
            return v
        return UUID(str(v))
