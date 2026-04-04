from __future__ import annotations

from typing import cast

from application.services.recipe_service import RecipeService
from arclith import Arclith, AdapterRegistry
from arclith.adapters.output.mongodb.config import MongoDBConfig
from arclith.domain.ports.logger import Logger
from arclith.domain.ports.repository import Repository
from arclith.infrastructure.config import AppConfig
from domain.models.recipe import Recipe
from domain.ports.output.recipe_repository import RecipeRepository


def _build_memory(cfg: AppConfig, log: Logger) -> Repository[Recipe]:
    from adapters.output.memory.repository import InMemoryRecipeRepository
    return InMemoryRecipeRepository()


def _build_mongodb(cfg: AppConfig, log: Logger) -> Repository[Recipe]:
    from adapters.output.mongodb.repository import MongoDBRecipeRepository
    mongo = cfg.adapters.mongodb
    if mongo is None:
        raise RuntimeError("MongoDB settings are required when repository=mongodb")
    return MongoDBRecipeRepository(
        MongoDBConfig(uri=mongo.uri, db_name=mongo.db_name),
        log,
    )


def _build_duckdb(cfg: AppConfig, log: Logger) -> Repository[Recipe]:
    from adapters.output.duckdb.repository import DuckDBRecipeRepository
    duckdb = cfg.adapters.duckdb
    if duckdb is None:
        raise RuntimeError("DuckDB settings are required when repository=duckdb")
    return DuckDBRecipeRepository(duckdb.path)


_registry = cast(
    AdapterRegistry[Recipe],
    AdapterRegistry[Recipe]()
    .register("memory", _build_memory)  # type: ignore[arg-type]
    .register("mongodb", _build_mongodb)  # type: ignore[arg-type]
    .register("duckdb", _build_duckdb)  # type: ignore[arg-type]
)


def build_recipe_service(arclith: Arclith) -> tuple[RecipeService, Logger]:
    arclith.logger.info("🗄️ Repository adapter selected", adapter=arclith.config.adapters.repository)
    repo: RecipeRepository = cast(RecipeRepository, _registry.build(arclith.config, arclith.logger))
    return RecipeService(repo, arclith.logger, arclith.config.soft_delete.retention_days), arclith.logger
