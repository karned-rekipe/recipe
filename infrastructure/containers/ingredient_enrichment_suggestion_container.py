from typing import cast

from application.services.ingredient_enrichment_suggestion_service import IngredientEnrichmentSuggestionService
from arclith import AdapterRegistry, Arclith
from arclith.adapters.output.mongodb.config import MongoDBConfig
from arclith.domain.ports.logger import Logger
from arclith.domain.ports.repository import Repository
from arclith.infrastructure.config import AppConfig
from domain.models.ingredient_enrichment_suggestion import IngredientEnrichmentSuggestion
from domain.ports.output.ingredient_enrichment_suggestion_repository import IngredientEnrichmentSuggestionRepository
from domain.ports.output.ingredient_repository import IngredientRepository


def _build_memory(cfg: AppConfig, log: Logger) -> Repository[IngredientEnrichmentSuggestion]:
    from adapters.output.memory.repositories.ingredient_enrichment_suggestion_repository import (
        InMemoryIngredientEnrichmentSuggestionRepository,
    )

    return InMemoryIngredientEnrichmentSuggestionRepository()


def _build_mongodb(cfg: AppConfig, log: Logger) -> Repository[IngredientEnrichmentSuggestion]:
    from adapters.output.mongodb.repositories.ingredient_enrichment_suggestion_repository import (
        MongoDBIngredientEnrichmentSuggestionRepository,
    )

    mongo = cfg.adapters.mongodb
    if mongo is None:
        raise RuntimeError("MongoDB settings are required when repository=mongodb")
    return MongoDBIngredientEnrichmentSuggestionRepository(
        MongoDBConfig(uri=mongo.uri, db_name=mongo.db_name, collection_name="ingredient_enrichment_suggestions"),
        log,
    )


def _build_duckdb(cfg: AppConfig, log: Logger) -> Repository[IngredientEnrichmentSuggestion]:
    from adapters.output.duckdb.repositories.ingredient_enrichment_suggestion_repository import (
        DuckDBIngredientEnrichmentSuggestionRepository,
    )

    duckdb = cfg.adapters.duckdb
    if duckdb is None:
        raise RuntimeError("DuckDB settings are required when repository=duckdb")
    return DuckDBIngredientEnrichmentSuggestionRepository(duckdb.path)


_registry = cast(
    AdapterRegistry[IngredientEnrichmentSuggestion],
    AdapterRegistry[IngredientEnrichmentSuggestion]()
    .register("memory", _build_memory)  # type: ignore[arg-type]
    .register("mongodb", _build_mongodb)  # type: ignore[arg-type]
    .register("duckdb", _build_duckdb),  # type: ignore[arg-type]
)


def build_ingredient_enrichment_suggestion_service(
    arclith: Arclith,
    ingredient_repository: IngredientRepository,
) -> tuple[IngredientEnrichmentSuggestionService, Logger]:
    repo: IngredientEnrichmentSuggestionRepository = cast(
        IngredientEnrichmentSuggestionRepository,
        _registry.build(arclith.config, arclith.logger),
    )
    return (
        IngredientEnrichmentSuggestionService(
            repo,
            ingredient_repository,
            arclith.logger,
            arclith.config.soft_delete.retention_days,
        ),
        arclith.logger,
    )
