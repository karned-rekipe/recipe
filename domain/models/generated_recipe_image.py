from pydantic import BaseModel, Field


class StoredRecipeImage(BaseModel):
    bucket: str
    key: str
    url: str
    content_type: str
    size_bytes: int = Field(ge=0)


class GeneratedRecipeImage(BaseModel):
    image: StoredRecipeImage
    provider: str
