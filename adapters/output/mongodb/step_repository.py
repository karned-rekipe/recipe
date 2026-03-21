import re
from typing import Any
from uuid import UUID as StdUUID

from arclith.adapters.output.mongodb.config import MongoDBConfig
from arclith.adapters.output.mongodb.repository import MongoDBRepository
from arclith.domain.ports.logger import Logger
from uuid6 import UUID

from domain.models.step import Step
from domain.ports.step_repository import StepRepository


class MongoDBStepRepository(MongoDBRepository[Step], StepRepository):
    def __init__(self, config: MongoDBConfig, logger: Logger) -> None:
        super().__init__(config, Step, logger)

    def _to_doc(self, entity: Step) -> dict[str, Any]:
        doc = super()._to_doc(entity)
        if isinstance(doc.get("recipe_uuid"), (UUID, StdUUID)):
            doc["recipe_uuid"] = str(doc["recipe_uuid"])
        return doc

    def _from_doc(self, doc: dict[str, Any]) -> Step:
        if isinstance(doc.get("recipe_uuid"), str):
            doc = {**doc, "recipe_uuid": UUID(doc["recipe_uuid"])}
        return super()._from_doc(doc)

    async def find_by_name(self, name: str) -> list[Step]:
        async with self._collection() as col:
            escaped_name = re.escape(name)
            return [
                self._from_doc(doc)
                async for doc in col.find(
                    {"name": {"$regex": escaped_name, "$options": "i"}, "deleted_at": None}
                )
            ]

    async def find_by_recipe(self, recipe_uuid: UUID) -> list[Step]:
        async with self._collection() as col:
            return [
                self._from_doc(doc)
                async for doc in col.find(
                    {"recipe_uuid": str(recipe_uuid), "deleted_at": None}
                )
            ]

