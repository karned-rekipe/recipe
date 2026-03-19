from arclith import Entity
from pydantic import Field, field_validator


class Ustensil(Entity):
    name: str = Field(
        ...,
        description="Nom de l'ustensil.",
        examples=["Fouet", "Spatule"]
    )

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Ustensil name cannot be empty")
        return stripped