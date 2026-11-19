from typing import cast

from application.services.ingredient_rayon_service import IngredientRayonService
from arclith import Arclith, AdapterRegistry
from arclith.adapters.output.mongodb.config import MongoDBConfig
from arclith.domain.ports.logger import Logger
from arclith.domain.ports.repository import Repository
from arclith.infrastructure.config import AppConfig
from domain.models.ingredient_rayon import IngredientRayon
from domain.ports.output.ingredient_rayon_repository import IngredientRayonRepository


def _build_memory(cfg: AppConfig, log: Logger) -> Repository[IngredientRayon]:
    from adapters.output.memory.repositories.ingredient_rayon_repository import InMemoryIngredientRayonRepository
    return InMemoryIngredientRayonRepository()


def _build_mongodb(cfg: AppConfig, log: Logger) -> Repository[IngredientRayon]:
    from adapters.output.mongodb.repositories.ingredient_rayon_repository import MongoDBIngredientRayonRepository
    mongo = cfg.adapters.mongodb
    if mongo is None:
        raise RuntimeError("MongoDB settings are required when repository=mongodb")
    return MongoDBIngredientRayonRepository(MongoDBConfig(uri=mongo.uri, db_name=mongo.db_name), log)


def _build_duckdb(cfg: AppConfig, log: Logger) -> Repository[IngredientRayon]:
    from adapters.output.duckdb.repositories.ingredient_rayon_repository import DuckDBIngredientRayonRepository
    duckdb = cfg.adapters.duckdb
    if duckdb is None:
        raise RuntimeError("DuckDB settings are required when repository=duckdb")
    return DuckDBIngredientRayonRepository(duckdb.path)


_registry = cast(
    AdapterRegistry[IngredientRayon],
    AdapterRegistry[IngredientRayon]()
    .register("memory", _build_memory)  # type: ignore[arg-type]
    .register("mongodb", _build_mongodb)  # type: ignore[arg-type]
    .register("duckdb", _build_duckdb)  # type: ignore[arg-type]
)


def build_ingredient_rayon_service(arclith: Arclith) -> tuple[IngredientRayonService, Logger]:
    arclith.logger.info("🗄️ Ingredient rayon repository adapter selected", adapter=arclith.config.adapters.repository)
    repo: IngredientRayonRepository = cast(IngredientRayonRepository, _registry.build(arclith.config, arclith.logger))
    return IngredientRayonService(repo, arclith.logger, arclith.config.soft_delete.retention_days), arclith.logger
