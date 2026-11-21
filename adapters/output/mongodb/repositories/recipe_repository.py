import re
from collections.abc import Mapping, Sequence
from typing import Any
from typing import cast

from arclith.adapters.output.mongodb.config import MongoDBConfig
from arclith.adapters.output.mongodb.repository import MongoDBRepository
from arclith.domain.ports.logger import Logger
from domain.models.recipe import Recipe, RecipeStatus
from domain.models.recipe_filters import RecipeFilters
from domain.ports.output.recipe_repository import RecipeRepository
from uuid6 import UUID


class MongoDBRecipeRepository(MongoDBRepository[Recipe], RecipeRepository):
    def __init__(self, config: MongoDBConfig, logger: Logger) -> None:
        super().__init__(config, Recipe, logger)

    def _to_doc(self, entity: Recipe) -> dict[str, Any]:
        doc = entity.model_dump(mode="json", exclude_computed_fields=True)
        doc["_id"] = doc.pop("uuid")
        if doc.get("legacy_id") is None:
            doc.pop("legacy_id", None)
        return doc

    async def find_by_name(self, name: str) -> list[Recipe]:
        async with self._collection() as col:
            escaped_name = re.escape(name)
            return [
                self._from_doc(doc)
                async for doc in col.find(
                    {"name": {"$regex": escaped_name, "$options": "i"}, "deleted_at": None}
                )
            ]

    async def find_page_by_name(self, name: str, offset: int = 0, limit: int | None = None) -> tuple[list[Recipe], int]:
        return await self.find_page_filtered(name=name, offset=offset, limit=limit)

    async def find_page_by_ingredient_uuid(
        self,
        ingredient_uuid: UUID,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Recipe], int]:
        return await self._find_page_by_reference("ingredients.ingredient_uuid", str(ingredient_uuid), offset, limit)

    async def find_page_by_equipment_uuid(
        self,
        equipment_uuid: UUID,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Recipe], int]:
        return await self._find_page_by_reference("equipment.equipment_uuid", str(equipment_uuid), offset, limit)

    async def find_page_by_tag_uuid(
        self,
        tag_uuid: UUID,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Recipe], int]:
        return await self.find_page_filtered(tag_uuid=tag_uuid, offset=offset, limit=limit)

    async def find_by_component_recipe_uuid(self, recipe_uuid: UUID) -> list[Recipe]:
        async with self._collection() as col:
            return [
                self._from_doc(doc)
                async for doc in col.find(
                    {"components.recipe_uuid": str(recipe_uuid), "deleted_at": None}
                )
            ]

    async def find_page_filtered(
        self,
        name: str | None = None,
        ingredient_uuid: UUID | None = None,
        equipment_uuid: UUID | None = None,
        tag_uuid: UUID | None = None,
        difficulty: int | None = None,
        origin_country: str | None = None,
        price: int | None = None,
        favorite: bool | None = None,
        season_month: int | None = None,
        status: RecipeStatus | None = None,
        meal_planner_eligible: bool | None = None,
        has_main_image: bool | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Recipe], int]:
        filters = RecipeFilters(
            name=name,
            ingredient_uuid=ingredient_uuid,
            equipment_uuid=equipment_uuid,
            tag_uuid=tag_uuid,
            difficulty=difficulty,
            origin_country=origin_country,
            price=price,
            favorite=favorite,
            season_month=season_month,
            status=status,
            meal_planner_eligible=meal_planner_eligible,
            has_main_image=has_main_image,
        )
        return await self._find_page_by_match(_recipe_filter_match(filters), offset, limit)

    async def exists_by_ingredient_uuid(self, ingredient_uuid: UUID) -> bool:
        async with self._collection() as col:
            return await col.find_one({"ingredients.ingredient_uuid": str(ingredient_uuid), "deleted_at": None}) is not None

    async def exists_by_equipment_uuid(self, equipment_uuid: UUID) -> bool:
        async with self._collection() as col:
            return await col.find_one({"equipment.equipment_uuid": str(equipment_uuid), "deleted_at": None}) is not None

    async def exists_by_tag_uuid(self, tag_uuid: UUID) -> bool:
        async with self._collection() as col:
            return await col.find_one({"tag_uuids": str(tag_uuid), "deleted_at": None}) is not None

    async def _find_page_by_reference(
        self,
        field_name: str,
        uuid: str,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Recipe], int]:
        return await self._find_page_by_match({field_name: uuid, "deleted_at": None}, offset, limit)

    async def _find_page_by_match(
        self,
        match: dict[str, Any],
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Recipe], int]:
        data_pipeline: list[dict] = [{"$skip": offset}]
        if limit is not None:
            data_pipeline.append({"$limit": limit})
        pipeline: Sequence[Mapping[str, Any]] = cast(
            Sequence[Mapping[str, Any]],
            [
                {"$match": match},
                {"$facet": {"data": data_pipeline, "total": [{"$count": "count"}]}},
            ],
        )
        async with self._collection() as col:
            result = await col.aggregate(pipeline).to_list(length=1)
        if not result:
            return [], 0
        facet = result[0]
        items = [self._from_doc(doc) for doc in facet.get("data", [])]
        total = facet["total"][0]["count"] if facet.get("total") else 0
        return items, total


def _recipe_filter_match(filters: RecipeFilters) -> dict[str, Any]:
    match: dict[str, Any] = {"deleted_at": None}
    for criterion in _mongo_filter_criteria(filters):
        match.update(criterion)
    return match


def _mongo_filter_criteria(filters: RecipeFilters) -> tuple[dict[str, Any], ...]:
    expected_status = RecipeStatus.active if filters.meal_planner_eligible else filters.status
    return (
        _optional_match("status", expected_status.value if expected_status is not None else None),
        _meal_planner_eligibility_match(filters.meal_planner_eligible),
        _main_image_match(filters.has_main_image),
        _name_match(filters.name),
        _optional_match("ingredients.ingredient_uuid", _uuid_text(filters.ingredient_uuid)),
        _optional_match("equipment.equipment_uuid", _uuid_text(filters.equipment_uuid)),
        _optional_match("tag_uuids", _uuid_text(filters.tag_uuid)),
        _optional_match("difficulty", filters.difficulty),
        _optional_match("origin_country", filters.origin_country),
        _optional_match("price", filters.price),
        _optional_match("favorite", filters.favorite),
        _season_match(filters.season_month),
    )


def _optional_match(field: str, value: Any | None) -> dict[str, Any]:
    return {} if value is None else {field: value}


def _meal_planner_eligibility_match(eligible: bool | None) -> dict[str, Any]:
    return {"ingredients.0": {"$exists": True}} if eligible else {}


def _main_image_match(has_main_image: bool | None) -> dict[str, Any]:
    if has_main_image is None:
        return {}
    if has_main_image:
        return {"main_image": {"$regex": r"\S"}}
    return {"main_image": {"$not": {"$regex": r"\S"}}}


def _name_match(name: str | None) -> dict[str, Any]:
    return {} if not name else {"name": {"$regex": re.escape(name), "$options": "i"}}


def _uuid_text(value: UUID | None) -> str | None:
    return str(value) if value is not None else None


def _season_match(month: int | None) -> dict[str, Any]:
    return {} if month is None else {f"season_months.{month}": {"$gte": 1}}
