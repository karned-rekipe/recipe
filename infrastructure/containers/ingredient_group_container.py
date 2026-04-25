from typing import cast

from application.services.ingredient_group_service import IngredientGroupService
from arclith import Arclith, AdapterRegistry
from arclith.adapters.output.mongodb.config import MongoDBConfig
from arclith.domain.ports.logger import Logger
from arclith.domain.ports.repository import Repository
from arclith.infrastructure.config import AppConfig
from domain.models.ingredient_group import IngredientGroup
from domain.ports.output.ingredient_group_repository import IngredientGroupRepository


def _build_memory(cfg: AppConfig, log: Logger) -> Repository[IngredientGroup]:
    from adapters.output.memory.repositories.ingredient_group_repository import InMemoryIngredientGroupRepository
    return InMemoryIngredientGroupRepository()


def _build_mongodb(cfg: AppConfig, log: Logger) -> Repository[IngredientGroup]:
    from adapters.output.mongodb.repositories.ingredient_group_repository import MongoDBIngredientGroupRepository
    mongo = cfg.adapters.mongodb
    if mongo is None:
        raise RuntimeError("MongoDB settings are required when repository=mongodb")
    return MongoDBIngredientGroupRepository(MongoDBConfig(uri=mongo.uri, db_name=mongo.db_name), log)


def _build_duckdb(cfg: AppConfig, log: Logger) -> Repository[IngredientGroup]:
    from adapters.output.duckdb.repositories.ingredient_group_repository import DuckDBIngredientGroupRepository
    duckdb = cfg.adapters.duckdb
    if duckdb is None:
        raise RuntimeError("DuckDB settings are required when repository=duckdb")
    return DuckDBIngredientGroupRepository(duckdb.path)


_registry = cast(
    AdapterRegistry[IngredientGroup],
    AdapterRegistry[IngredientGroup]()
    .register("memory", _build_memory)  # type: ignore[arg-type]
    .register("mongodb", _build_mongodb)  # type: ignore[arg-type]
    .register("duckdb", _build_duckdb)  # type: ignore[arg-type]
)


def build_ingredient_group_service(arclith: Arclith) -> tuple[IngredientGroupService, Logger]:
    arclith.logger.info("🗄️ Ingredient group repository adapter selected", adapter=arclith.config.adapters.repository)
    repo: IngredientGroupRepository = cast(IngredientGroupRepository, _registry.build(arclith.config, arclith.logger))
    return IngredientGroupService(repo, arclith.logger, arclith.config.soft_delete.retention_days), arclith.logger
