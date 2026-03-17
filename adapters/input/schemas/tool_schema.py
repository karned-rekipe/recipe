from pydantic import BaseModel
from typing import Optional

from arclith.adapters.input.schemas.base_schema import BaseSchema


class ToolCreateSchema(BaseModel):
    name: str


class ToolPatchSchema(BaseModel):
    name: str


class ToolUpdateSchema(BaseModel):
    name: str


class ToolSchema(BaseSchema):
    name: str

