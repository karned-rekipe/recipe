from arclith import Arclith
from arclith.adapters.output.mongodb.config import MongoDBConfig
from arclith.domain.ports.logger import Logger
from application.services.tool_service import ToolService


def build_tool_service(arclith: Arclith) -> tuple[ToolService, Logger]:
    config = arclith.config
    match config.adapters.repository:
        case "mongodb":
            from adapters.output.mongodb.repository import MongoDBToolRepository
            mongo = config.adapters.mongodb
            repo = MongoDBToolRepository(
                MongoDBConfig(uri=mongo.uri, db_name=mongo.db_name),
                arclith.logger,
            )
        case "duckdb":
            from adapters.output.duckdb.repository import DuckDBToolRepository
            repo = DuckDBToolRepository(config.adapters.duckdb.path)
        case _:
            from adapters.output.memory.repository import InMemoryToolRepository
            repo = InMemoryToolRepository()
    return ToolService(repo, arclith.logger, config.soft_delete.retention_days), arclith.logger

