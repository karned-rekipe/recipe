from pydantic import BaseModel, Field


class StoredImage(BaseModel):
    bucket: str
    key: str
    url: str
    content_type: str
    size_bytes: int = Field(ge=0)


class GeneratedImage(BaseModel):
    image: StoredImage
    provider: str
