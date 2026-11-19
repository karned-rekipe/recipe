import re
from collections.abc import Mapping, Sequence
from typing import Any, cast

from arclith.adapters.output.mongodb.config import MongoDBConfig
from arclith.adapters.output.mongodb.repository import MongoDBRepository
from arclith.domain.ports.logger import Logger
from domain.models.ingredient_rayon import IngredientRayon
from domain.ports.output.ingredient_rayon_repository import IngredientRayonRepository


class MongoDBIngredientRayonRepository(MongoDBRepository[IngredientRayon], IngredientRayonRepository):
    def __init__(self, config: MongoDBConfig, logger: Logger) -> None:
        super().__init__(
            MongoDBConfig(uri=config.uri, db_name=config.db_name, collection_name="ingredient_rayon"),
            IngredientRayon,
            logger,
        )

    async def find_by_name(self, name: str) -> list[IngredientRayon]:
        async with self._collection() as col:
            escaped_name = re.escape(name)
            return [
                self._from_doc(doc)
                async for doc in col.find({"name": {"$regex": escaped_name, "$options": "i"}, "deleted_at": None})
            ]

    async def find_page_by_name(
        self,
        name: str,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[IngredientRayon], int]:
        escaped_name = re.escape(name)
        data_pipeline: list[dict] = [{"$skip": offset}]
        if limit is not None:
            data_pipeline.append({"$limit": limit})
        pipeline: Sequence[Mapping[str, Any]] = cast(
            Sequence[Mapping[str, Any]],
            [
                {"$match": {"name": {"$regex": escaped_name, "$options": "i"}, "deleted_at": None}},
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
