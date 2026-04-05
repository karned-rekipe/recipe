from pydantic import ConfigDict, Field

from arclith.adapters.input.schemas.base_schema import BaseSchema


class StepSchema(BaseSchema):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [{
                "uuid": "01951234-0001-7abc-def0-000000000001",
                "created_at": "2026-03-17T10:00:00+00:00",
                "updated_at": "2026-03-17T10:00:00+00:00",
                "created_by": None,
                "updated_by": None,
                "deleted_at": None,
                "deleted_by": None,
                "is_deleted": False,
                "version": 1,
                "name": "Préparer la pâte",
                "description": "Mélanger farine, eau, levure et sel jusqu'à obtenir une pâte lisse.",
                "cooking_time": None,
                "rest_time": 60,
                "preparation_time": 15,
                "main_image": None,
                "secondary_images": [],
                "rank": 1,
                "total_time": 75,
            }]
        },
    )

    name: str
    description: str | None = None
    cooking_time: int | None = Field(None, ge=0)
    rest_time: int | None = Field(None, ge=0)
    preparation_time: int | None = Field(None, ge=0)
    main_image: str | None = None
    secondary_images: list[str] = []
    rank: int = Field(..., ge=1)
    total_time: int
