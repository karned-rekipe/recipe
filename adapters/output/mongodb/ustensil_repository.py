from arclith.adapters.output.mongodb.config import MongoDBConfig
from arclith.adapters.output.mongodb.repository import MongoDBRepository
from arclith.domain.ports.logger import Logger
import re

from domain.models.ustensil import Ustensil
from domain.ports.ustensil_repository import UstensilRepository


class MongoDBUstensilRepository(MongoDBRepository[Ustensil], UstensilRepository):
    def __init__(self, config: MongoDBConfig, logger: Logger) -> None:
        super().__init__(config, Ustensil, logger)

    async def find_by_name(self, name: str) -> list[Ustensil]:
        async with self._collection() as col:
            escaped_name = re.escape(name)
            return [
                self._from_doc(doc)
                async for doc in col.find(
                    {"name": {"$regex": escaped_name, "$options": "i"}, "deleted_at": None}
                )
            ]
