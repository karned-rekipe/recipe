from arclith import Arclith
from arclith.adapters.output.mongodb.config import MongoDBConfig
from arclith.domain.ports.logger import Logger

from application.services.ustensil_service import UstensilService
from domain.ports.output.ustensil_repository import UstensilRepository


def build_ustensil_service(arclith: Arclith) -> tuple[UstensilService, Logger]:
    config = arclith.config
    repo: UstensilRepository
    match config.adapters.repository:
        case "mongodb":
            from adapters.output.mongodb.repositories.ustensil_repository import MongoDBUstensilRepository
            assert config.adapters.mongodb is not None
            mongo = config.adapters.mongodb
            repo = MongoDBUstensilRepository(
                MongoDBConfig(uri = mongo.uri, db_name = mongo.db_name),
                arclith.logger,
            )
        case "duckdb":
            from adapters.output.duckdb.repositories.ustensil_repository import DuckDBUstensilRepository
            assert config.adapters.duckdb is not None
            repo = DuckDBUstensilRepository(config.adapters.duckdb.path)
        case _:
            from adapters.output.memory.repositories.ustensil_repository import InMemoryUstensilRepository
            repo = InMemoryUstensilRepository()
    return UstensilService(repo, arclith.logger, config.soft_delete.retention_days), arclith.logger
