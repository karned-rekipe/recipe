import re
from datetime import datetime, timezone
from typing import Any

from arclith.adapters.output.mongodb.config import MongoDBConfig
from arclith.adapters.output.mongodb.repository import MongoDBRepository
from arclith.domain.ports.logger import Logger
from domain.models.equipment import Equipment
from domain.ports.output.equipment_repository import EquipmentRepository
from pymongo import ReturnDocument
from uuid6 import UUID


class MongoDBEquipmentRepository(MongoDBRepository[Equipment], EquipmentRepository):
    def __init__(self, config: MongoDBConfig, logger: Logger) -> None:
        super().__init__(config, Equipment, logger)

    async def reserve_image_generation(
        self,
        equipment_uuid: UUID,
        reservation_id: str,
        expires_at: datetime,
        *,
        replace_existing: bool,
    ) -> Equipment | None:
        match: dict[str, Any] = {
            "_id": str(equipment_uuid),
            "deleted_at": None,
            "$or": [
                {"image_generation_reservation": {"$exists": False}},
                {"image_generation_reservation.expires_at": {"$lte": datetime.now(timezone.utc)}},
            ],
        }
        if not replace_existing:
            match["main_image"] = {"$not": {"$regex": r"\S"}}
        async with self._collection() as col:
            doc = await col.find_one_and_update(
                match,
                {"$set": {"image_generation_reservation": {"id": reservation_id, "expires_at": expires_at}}},
                return_document=ReturnDocument.AFTER,
            )
        return self._from_doc(doc) if doc is not None else None

    async def complete_image_generation(
        self,
        equipment_uuid: UUID,
        reservation_id: str,
        image_url: str,
        *,
        replace_existing: bool,
    ) -> Equipment | None:
        match: dict[str, Any] = {
            "_id": str(equipment_uuid),
            "deleted_at": None,
            "image_generation_reservation.id": reservation_id,
        }
        if not replace_existing:
            match["main_image"] = {"$not": {"$regex": r"\S"}}
        async with self._collection() as col:
            doc = await col.find_one_and_update(
                match,
                {
                    "$set": {
                        "main_image": image_url,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                    "$inc": {"version": 1},
                    "$unset": {"image_generation_reservation": ""},
                },
                return_document=ReturnDocument.AFTER,
            )
        return self._from_doc(doc) if doc is not None else None

    async def release_image_generation(self, equipment_uuid: UUID, reservation_id: str) -> None:
        async with self._collection() as col:
            await col.update_one(
                {
                    "_id": str(equipment_uuid),
                    "image_generation_reservation.id": reservation_id,
                },
                {"$unset": {"image_generation_reservation": ""}},
            )

    async def find_by_name(self, name: str) -> list[Equipment]:
        async with self._collection() as col:
            escaped_name = re.escape(name)
            return [
                self._from_doc(doc)
                async for doc in col.find(
                    {"name": {"$regex": escaped_name, "$options": "i"}, "deleted_at": None}
                )
            ]

    async def find_page_by_name(self, name: str, offset: int = 0, limit: int | None = None) -> tuple[list[Equipment], int]:
        """Single-query pagination with name filter via $facet."""
        from collections.abc import Mapping, Sequence
        from typing import Any, cast

        escaped_name = re.escape(name)
        data_pipeline: list[dict] = [{"$skip": offset}]
        if limit is not None:
            data_pipeline.append({"$limit": limit})
        pipeline: Sequence[Mapping[str, Any]] = cast(
            Sequence[Mapping[str, Any]],
            [
                {"$match": {"name": {"$regex": escaped_name, "$options": "i"}, "deleted_at": None}},
                {"$facet": {
                    "data": data_pipeline,
                    "total": [{"$count": "count"}],
                }},
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
