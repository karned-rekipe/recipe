from arclith import Entity
from pydantic import Field, field_validator


class Step(Entity):
    name: str = Field(
        ...,
        max_length=80,
        description="Nom de l'étape",
        examples=["Préparer la pâte", "Cuire la pizza"])
    description: str | None = Field(
        None,
        description="La description détaillée de l'étape. None si non applicable.",
        examples=[
            "Mélanger la farine, l'eau et la levure pour préparer la pâte.",
            "Cuire la pizza au four à 220°C pendant 15 minutes.",
            None])


    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Step name cannot be empty")
        return stripped
