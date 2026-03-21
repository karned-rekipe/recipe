from arclith import Arclith
from arclith.adapters.output.mongodb.config import MongoDBConfig
from arclith.domain.ports.logger import Logger
from application.services.ingredient_service import IngredientService
from application.services.recipe_service import RecipeService


def build_recipe_service(arclith: Arclith) -> tuple[RecipeService, Logger]:
    config = arclith.config
    match config.adapters.repository:
        case "mongodb":
            from adapters.output.mongodb.repository import MongoDBRecipeRepository
            mongo = config.adapters.mongodb
            repo = MongoDBRecipeRepository(
                MongoDBConfig(uri=mongo.uri, db_name=mongo.db_name),
                arclith.logger,
            )
        case "duckdb":
            from adapters.output.duckdb.repository import DuckDBRecipeRepository
            repo = DuckDBRecipeRepository(config.adapters.duckdb.path)
        case _:
            from adapters.output.memory.repository import InMemoryRecipeRepository
            repo = InMemoryRecipeRepository()
    return RecipeService(repo, arclith.logger, config.soft_delete.retention_days), arclith.logger

