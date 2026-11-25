from pydantic import Field, field_validator

from arclith.domain.models.entity import Entity


class Equipment(Entity):
    name: str = Field(
        ...,
        description="Equipment name, normalized (leading/trailing spaces removed).",
        examples=["Four", "Saladier"],
    )
    description: str | None = Field(
        None,
        description="Optional equipment details.",
        examples=["Robot multifonction, bol 2 L"],
    )
    main_image: str | None = Field(
        None,
        description="Public URL of the generated main image.",
    )

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Equipment name cannot be empty")
        return stripped
