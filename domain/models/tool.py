from arclith import Entity
from pydantic import Field, field_validator


class Tool(Entity):
    name: str = Field(
        ...,
        description="Nom de l'outil.",
        examples=["Pizza maker", "Salad maker"]
    )

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Ingredient name cannot be empty")
        return stripped