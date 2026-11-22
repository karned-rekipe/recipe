from pydantic import BaseModel, Field


class RecipeAIEnrichment(BaseModel):
    """Outcome returned by the internal recipe-creator agent."""

    recipe_uuid: str
    recipe_name: str
    formatted_response: str
    updated: bool = True
    image_generated: bool = False
    warnings: list[str] = Field(default_factory=list)
