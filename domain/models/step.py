from pydantic import Field, computed_field, field_validator

from arclith.domain.models.entity import Entity
from domain.models.recipe_line_origin import RecipeLineOrigin
from uuid6 import UUID


class Step(Entity):
    name: str = Field(..., examples=["Prepare the dough", "Bake in the oven"])
    description: str | None = Field(None, examples=["Mix flour and water until smooth.", "Preheat oven to 200°C and bake for 25 minutes."])
    cooking_time: int | None = Field(None, description="Cooking time in minutes.", ge=0, examples=[25, 10])
    rest_time: int | None = Field(None, description="Rest time in minutes.", ge=0, examples=[60, 0])
    preparation_time: int | None = Field(None, description="Preparation time in minutes.", ge=0, examples=[15, 5])
    secondary_images: list[str] = Field(default_factory=list, examples=[["https://example.com/step1b.jpg"]])
    main_image: str | None = Field(None, examples=["https://example.com/step1.jpg"])
    rank: int = Field(..., description="Order of the step in the recipe.", ge=1, examples=[1, 2, 3])
    component_uuid: UUID | None = Field(
        None,
        description="Parent embedded component UUID when this step is projected from a sub-recipe.",
    )
    source_recipe_uuid: UUID | None = Field(
        None,
        description="Child recipe UUID when this step is projected from a sub-recipe.",
    )
    line_origin: RecipeLineOrigin = Field(
        RecipeLineOrigin.manual,
        description="Whether the step is manually owned by the recipe or projected from a component.",
    )

    @field_validator("component_uuid", "source_recipe_uuid", mode="before")
    @classmethod
    def coerce_optional_uuid(cls, value: object) -> UUID | None:
        if value is None:
            return None
        if isinstance(value, UUID):
            return value
        return UUID(str(value))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_time(self) -> int:
        return (self.cooking_time or 0) + (self.rest_time or 0) + (self.preparation_time or 0)
