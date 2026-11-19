from typing import cast

from application.services.tag_service import TagService
from arclith import Arclith, AdapterRegistry
from arclith.adapters.output.mongodb.config import MongoDBConfig
from arclith.domain.ports.logger import Logger
from arclith.domain.ports.repository import Repository
from arclith.infrastructure.config import AppConfig
from domain.models.tag import Tag
from domain.ports.output.tag_repository import TagRepository


def _build_memory(cfg: AppConfig, log: Logger) -> Repository[Tag]:
    from adapters.output.memory.repositories.tag_repository import InMemoryTagRepository
    return InMemoryTagRepository()


def _build_mongodb(cfg: AppConfig, log: Logger) -> Repository[Tag]:
    from adapters.output.mongodb.repositories.tag_repository import MongoDBTagRepository
    mongo = cfg.adapters.mongodb
    if mongo is None:
        raise RuntimeError("MongoDB settings are required when repository=mongodb")
    return MongoDBTagRepository(MongoDBConfig(uri=mongo.uri, db_name=mongo.db_name), log)


def _build_duckdb(cfg: AppConfig, log: Logger) -> Repository[Tag]:
    from adapters.output.duckdb.repositories.tag_repository import DuckDBTagRepository
    duckdb = cfg.adapters.duckdb
    if duckdb is None:
        raise RuntimeError("DuckDB settings are required when repository=duckdb")
    return DuckDBTagRepository(duckdb.path)


_registry = cast(
    AdapterRegistry[Tag],
    AdapterRegistry[Tag]()
    .register("memory", _build_memory)  # type: ignore[arg-type]
    .register("mongodb", _build_mongodb)  # type: ignore[arg-type]
    .register("duckdb", _build_duckdb)  # type: ignore[arg-type]
)


def build_tag_service(arclith: Arclith) -> tuple[TagService, Logger]:
    arclith.logger.info("🗄️ Tag repository adapter selected", adapter=arclith.config.adapters.repository)
    repo: TagRepository = cast(TagRepository, _registry.build(arclith.config, arclith.logger))
    return TagService(repo, arclith.logger, arclith.config.soft_delete.retention_days), arclith.logger
