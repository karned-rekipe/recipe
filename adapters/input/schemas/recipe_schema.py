from pydantic import BaseModel
from typing import Optional

from arclith.adapters.input.schemas.base_schema import BaseSchema


class RecipeCreateSchema(BaseModel):
    name: str
    description: Optional[str] = None


class RecipePatchSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class RecipeUpdateSchema(BaseModel):
    name: str
    description: Optional[str] = None


class RecipeSchema(BaseSchema):
    name: str
    description: Optional[str] = None

