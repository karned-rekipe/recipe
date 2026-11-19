import re
from collections.abc import Mapping, Sequence
from typing import Any, cast

from arclith.adapters.output.mongodb.config import MongoDBConfig
from arclith.adapters.output.mongodb.repository import MongoDBRepository
from arclith.domain.ports.logger import Logger
from domain.models.ingredient import Ingredient
from domain.ports.output.ingredient_repository import IngredientRepository
from uuid6 import UUID


class MongoDBIngredientRepository(MongoDBRepository[Ingredient], IngredientRepository):
    def __init__(self, config: MongoDBConfig, logger: Logger) -> None:
        super().__init__(config, Ingredient, logger)

    def _to_doc(self, entity: Ingredient) -> dict[str, Any]:
        doc = entity.model_dump(mode="json", exclude_computed_fields=True)
        doc["_id"] = doc.pop("uuid")
        return doc

    async def find_by_name(self, name: str) -> list[Ingredient]:
        async with self._collection() as col:
            escaped_name = re.escape(name)
            return [
                self._from_doc(doc)
                async for doc in col.find(
                    {"name": {"$regex": escaped_name, "$options": "i"}, "deleted_at": None}
                )
            ]

    async def find_page_by_name(self, name: str, offset: int = 0, limit: int | None = None) -> tuple[list[Ingredient], int]:
        return await self.find_page_filtered(name=name, offset=offset, limit=limit)

    async def find_page_filtered(
        self,
        name: str | None = None,
        group_uuid: UUID | None = None,
        rayon_uuid: UUID | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Ingredient], int]:
        match: dict[str, Any] = {"deleted_at": None}
        if name:
            match["name"] = {"$regex": re.escape(name), "$options": "i"}
        if group_uuid is not None:
            match["group_uuid"] = str(group_uuid)
        if rayon_uuid is not None:
            match["rayon_uuid"] = str(rayon_uuid)
        data_pipeline: list[dict] = [{"$skip": offset}]
        if limit is not None:
            data_pipeline.append({"$limit": limit})
        pipeline: Sequence[Mapping[str, Any]] = cast(
            Sequence[Mapping[str, Any]],
            [
                {"$match": match},
                {"$facet": {
                    "data": data_pipeline,
                    "total": [{"$count": "count"}],
                }},
            ]
        )
        async with self._collection() as col:
            result = await col.aggregate(pipeline).to_list(length=1)
        if not result:
            return [], 0
        facet = result[0]
        items = [self._from_doc(doc) for doc in facet.get("data", [])]
        total = facet["total"][0]["count"] if facet.get("total") else 0
        return items, total

    async def exists_by_group_uuid(self, group_uuid: UUID) -> bool:
        async with self._collection() as col:
            return await col.find_one({"group_uuid": str(group_uuid), "deleted_at": None}) is not None

    async def exists_by_rayon_uuid(self, rayon_uuid: UUID) -> bool:
        async with self._collection() as col:
            return await col.find_one({"rayon_uuid": str(rayon_uuid), "deleted_at": None}) is not None
