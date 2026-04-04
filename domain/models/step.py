from pydantic import Field, computed_field

from arclith.domain.models.entity import Entity


class Step(Entity):
    name: str = Field(..., examples=["Prepare the dough", "Bake in the oven"])
    description: str | None = Field(None, examples=["Mix flour and water until smooth.", "Preheat oven to 200°C and bake for 25 minutes."])
    cooking_time: int | None = Field(None, description="Cooking time in minutes.", ge=0, examples=[25, 10])
    rest_time: int | None = Field(None, description="Rest time in minutes.", ge=0, examples=[60, 0])
    preparation_time: int | None = Field(None, description="Preparation time in minutes.", ge=0, examples=[15, 5])
    secondary_images: list[str] = Field(default_factory=list, examples=[["https://example.com/step1b.jpg"]])
    main_image: str | None = Field(None, examples=["https://example.com/step1.jpg"])
    rank: int = Field(..., description="Order of the step in the recipe.", ge=1, examples=[1, 2, 3])

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_time(self) -> int:
        return (self.cooking_time or 0) + (self.rest_time or 0) + (self.preparation_time or 0)
