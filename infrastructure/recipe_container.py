from arclith import Arclith
from arclith.adapters.output.mongodb.config import MongoDBConfig
from arclith.domain.ports.logger import Logger

from application.services.recipe_service import RecipeService
from domain.ports.ingredient_repository import IngredientRepository
from domain.ports.recipe_repository import RecipeRepository
from domain.ports.ustensil_repository import UstensilRepository


def build_recipe_service(arclith: Arclith) -> tuple[RecipeService, Logger]:
    config = arclith.config
    repo: RecipeRepository
    ingredient_repo: IngredientRepository
    ustensil_repo: UstensilRepository
    match config.adapters.repository:
        case "mongodb":
            from adapters.output.mongodb.recipe_repository import MongoDBRecipeRepository
            from adapters.output.mongodb.ingredient_repository import MongoDBIngredientRepository
            from adapters.output.mongodb.ustensil_repository import MongoDBUstensilRepository
            assert config.adapters.mongodb is not None
            mongo_config = MongoDBConfig(uri = config.adapters.mongodb.uri, db_name = config.adapters.mongodb.db_name)
            repo = MongoDBRecipeRepository(mongo_config, arclith.logger)
            ingredient_repo = MongoDBIngredientRepository(mongo_config, arclith.logger)
            ustensil_repo = MongoDBUstensilRepository(mongo_config, arclith.logger)
        case "duckdb":
            from adapters.output.duckdb.recipe_repository import DuckDBRecipeRepository
            from adapters.output.duckdb.ingredient_repository import DuckDBIngredientRepository
            from adapters.output.duckdb.ustensil_repository import DuckDBUstensilRepository
            assert config.adapters.duckdb is not None
            repo = DuckDBRecipeRepository(config.adapters.duckdb.path)
            ingredient_repo = DuckDBIngredientRepository(config.adapters.duckdb.path)
            ustensil_repo = DuckDBUstensilRepository(config.adapters.duckdb.path)
        case _:
            from adapters.output.memory.recipe_repository import InMemoryRecipeRepository
            from adapters.output.memory.ingredient_repository import InMemoryIngredientRepository
            from adapters.output.memory.ustensil_repository import InMemoryUstensilRepository
            repo = InMemoryRecipeRepository()
            ingredient_repo = InMemoryIngredientRepository()
            ustensil_repo = InMemoryUstensilRepository()
    return RecipeService(repo, ingredient_repo, ustensil_repo, arclith.logger,
                         config.soft_delete.retention_days), arclith.logger
