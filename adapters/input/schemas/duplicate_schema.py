from uuid import UUID as StdUUID

from pydantic import BaseModel, Field


class DuplicateItemSchema(BaseModel):
    uuid: StdUUID = Field(..., description="UUID of the duplicate candidate.")
    name: str = Field(..., description="Display name of the duplicate candidate.")


class DuplicateGroupSchema(BaseModel):
    normalized_name: str = Field(..., description="Normalized duplicate key.")
    items: list[DuplicateItemSchema] = Field(..., min_length=2, description="Candidates sharing the same normalized name.")


class DuplicateMergeSchema(BaseModel):
    target_uuid: StdUUID = Field(..., description="Canonical UUID kept after merge.")
    duplicate_uuids: list[StdUUID] = Field(..., min_length=1, description="Duplicate UUIDs merged into the target.")


class DuplicateMergeResultSchema(BaseModel):
    target_uuid: StdUUID = Field(..., description="Canonical UUID kept after merge.")
    merged_uuids: list[StdUUID] = Field(default_factory=list, description="Soft-deleted duplicate UUIDs.")
    updated_recipe_count: int = Field(0, ge=0, description="Number of recipes rewritten.")
    deleted_count: int = Field(0, ge=0, description="Number of duplicate resources soft-deleted.")
