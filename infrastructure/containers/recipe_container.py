from __future__ import annotations

from typing import cast

from application.services.recipe_service import RecipeService
from arclith import Arclith, AdapterRegistry
from arclith.adapters.output.mongodb.config import MongoDBConfig
from arclith.domain.ports.logger import Logger
from arclith.domain.ports.repository import Repository
from arclith.infrastructure.config import AppConfig
from domain.models.recipe import Recipe
from domain.ports.output.equipment_repository import EquipmentRepository
from domain.ports.output.ingredient_group_repository import IngredientGroupRepository
from domain.ports.output.ingredient_repository import IngredientRepository
from domain.ports.output.ingredient_rayon_repository import IngredientRayonRepository
from domain.ports.output.recipe_repository import RecipeRepository
from domain.ports.output.image_generator import ImageGenerator
from domain.ports.output.recipe_ai_enrichment_agent import RecipeAIEnrichmentAgent
from domain.ports.output.tag_repository import TagRepository


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


def build_recipe_service(
    arclith: Arclith,
    ingredient_repository: IngredientRepository | None = None,
    equipment_repository: EquipmentRepository | None = None,
    tag_repository: TagRepository | None = None,
    group_repository: IngredientGroupRepository | None = None,
    rayon_repository: IngredientRayonRepository | None = None,
    image_generator: ImageGenerator | None = None,
    ai_enrichment_agent: RecipeAIEnrichmentAgent | None = None,
) -> tuple[RecipeService, Logger]:
    arclith.logger.info("🗄️ Repository adapter selected", adapter=arclith.config.adapters.repository)
    repo: RecipeRepository = cast(RecipeRepository, _registry.build(arclith.config, arclith.logger))
    return RecipeService(
        repo,
        arclith.logger,
        arclith.config.soft_delete.retention_days,
        ingredient_repository=ingredient_repository,
        equipment_repository=equipment_repository,
        tag_repository=tag_repository,
        group_repository=group_repository,
        rayon_repository=rayon_repository,
        image_generator=image_generator,
        ai_enrichment_agent=ai_enrichment_agent,
    ), arclith.logger
