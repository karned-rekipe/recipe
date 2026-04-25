from __future__ import annotations

from typing import cast

from application.services.equipment_service import EquipmentService
from arclith import Arclith, AdapterRegistry
from arclith.adapters.output.mongodb.config import MongoDBConfig
from arclith.domain.ports.logger import Logger
from arclith.domain.ports.repository import Repository
from arclith.infrastructure.config import AppConfig
from domain.models.equipment import Equipment
from domain.ports.output.equipment_repository import EquipmentRepository


def _build_memory(cfg: AppConfig, log: Logger) -> Repository[Equipment]:
    from adapters.output.memory.repositories.equipment_repository import InMemoryEquipmentRepository
    return InMemoryEquipmentRepository()


def _build_mongodb(cfg: AppConfig, log: Logger) -> Repository[Equipment]:
    from adapters.output.mongodb.repositories.equipment_repository import MongoDBEquipmentRepository
    mongo = cfg.adapters.mongodb
    if mongo is None:
        raise RuntimeError("MongoDB settings are required when repository=mongodb")
    return MongoDBEquipmentRepository(
        MongoDBConfig(uri=mongo.uri, db_name=mongo.db_name),
        log,
    )


def _build_duckdb(cfg: AppConfig, log: Logger) -> Repository[Equipment]:
    from adapters.output.duckdb.repositories.equipment_repository import DuckDBEquipmentRepository
    duckdb = cfg.adapters.duckdb
    if duckdb is None:
        raise RuntimeError("DuckDB settings are required when repository=duckdb")
    return DuckDBEquipmentRepository(duckdb.path)


_registry = cast(
    AdapterRegistry[Equipment],
    AdapterRegistry[Equipment]()
    .register("memory", _build_memory)  # type: ignore[arg-type]
    .register("mongodb", _build_mongodb)  # type: ignore[arg-type]
    .register("duckdb", _build_duckdb)  # type: ignore[arg-type]
)


def build_equipment_service(arclith: Arclith) -> tuple[EquipmentService, Logger]:
    arclith.logger.info("🗄️ Equipment repository adapter selected", adapter=arclith.config.adapters.repository)
    repo: EquipmentRepository = cast(EquipmentRepository, _registry.build(arclith.config, arclith.logger))
    return EquipmentService(repo, arclith.logger, arclith.config.soft_delete.retention_days), arclith.logger
