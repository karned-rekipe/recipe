from arclith import Arclith
from arclith.adapters.output.mongodb.config import MongoDBConfig
from arclith.domain.ports.logger import Logger
from application.services.step_service import StepService


def build_step_service(arclith: Arclith) -> tuple[StepService, Logger]:
    config = arclith.config
    match config.adapters.repository:
        case "mongodb":
            from adapters.output.mongodb.repository import MongoDBStepRepository
            mongo = config.adapters.mongodb
            repo = MongoDBStepRepository(
                MongoDBConfig(uri=mongo.uri, db_name=mongo.db_name),
                arclith.logger,
            )
        case "duckdb":
            from adapters.output.duckdb.repository import DuckDBStepRepository
            repo = DuckDBStepRepository(config.adapters.duckdb.path)
        case _:
            from adapters.output.memory.repository import InMemoryStepRepository
            repo = InMemoryStepRepository()
    return StepService(repo, arclith.logger, config.soft_delete.retention_days), arclith.logger

