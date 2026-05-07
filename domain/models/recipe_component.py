from pydantic import BaseModel, ConfigDict, Field, field_validator
from uuid6 import UUID, uuid7


class RecipeComponent(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    uuid: UUID = Field(default_factory=uuid7, description="Embedded component UUID.")
    recipe_uuid: UUID = Field(..., description="Referenced child recipe UUID.")
    label: str = Field(..., min_length=1, description="Display label for the child recipe in the parent.")
    rank: int = Field(..., ge=1, description="Display order in the parent recipe.")
    servings_multiplier: float = Field(1.0, gt=0, description="Quantity multiplier applied to projected child lines.")

    @field_validator("uuid", "recipe_uuid", mode="before")
    @classmethod
    def coerce_uuid(cls, v: object) -> UUID:
        if isinstance(v, UUID):
            return v
        return UUID(str(v))

    @field_validator("label", mode="before")
    @classmethod
    def strip_label(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Component label cannot be empty")
        return stripped
