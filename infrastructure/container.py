from dataclasses import dataclass

from arclith import Arclith, MongoDBConfig

# from adapters.output.duckdb.repository import DuckDBRecipeRepository, DuckDBToolRepository
from adapters.output.mongodb.repository import MongoDBToolRepository, MongoDBRecipeRepository
from application.services.recipe_service import RecipeService
from application.services.tool_service import ToolService
from domain.ports.ingredient_repository import IngredientRepository
from application.services.ingredient_service import IngredientService
from logging import Logger

from domain.ports.recipe_repository import RecipeRepository
from domain.ports.tool_repository import ToolRepository


@dataclass
class AppServices:
    ingredient: IngredientService
    recipe: RecipeService
    tool: ToolService
    logger: Logger



def build_service(arclith: Arclith) -> AppServices:
    logger = arclith.logger
    config = arclith.config
    retention_days = config.soft_delete.retention_days


    match config.adapters.repository:
        case "mongodb":
            from adapters.output.mongodb.repository import MongoDBIngredientRepository
            mongo = getattr(config.adapters, "mongodb", None)
            if mongo is None:
                raise ValueError(
                    "MongoDB adapter configuration 'adapters.mongodb' is required when "
                    "'adapters.repository' is set to 'mongodb'."
                )
            ingredient_repo: IngredientRepository = MongoDBIngredientRepository(
                MongoDBConfig(uri=mongo.uri, db_name=mongo.db_name, collection_name=mongo.collection_name),
                logger,
            )
            tool_repo: ToolRepository = MongoDBToolRepository(
                MongoDBConfig(uri=mongo.uri, db_name=mongo.db_name, collection_name=mongo.collection_name),
                logger,
            )
            recipe_repo: RecipeRepository = MongoDBRecipeRepository(
                MongoDBConfig(uri=mongo.uri, db_name=mongo.db_name, collection_name=mongo.collection_name),
                logger,
            )

        # case "duckdb":
        #     from adapters.output.duckdb.repository import DuckDBIngredientRepository
        #     duckdb_config = getattr(config.adapters, "duckdb", None)
        #     if duckdb_config is None or getattr(duckdb_config, "path", None) is None:
        #         raise ValueError(
        #             "Invalid configuration: adapters.repository is 'duckdb' but "
        #             "config.adapters.duckdb.path is not set."
        #         )
        #     repo = DuckDBIngredientRepository(duckdb_config.path)

        case _:
            from adapters.output.memory.repository import InMemoryIngredientRepository
            from adapters.output.memory.repository import InMemoryToolRepository
            from adapters.output.memory.repository import InMemoryRecipeRepository

            ingredient_repo = InMemoryIngredientRepository()
            recipe_repo = InMemoryRecipeRepository()
            tool_repo = InMemoryToolRepository()

    return AppServices(
        ingredient=IngredientService(ingredient_repo, logger, retention_days),
        recipe=RecipeService(recipe_repo, logger, retention_days),
        tool=ToolService(tool_repo, logger, retention_days),
        logger=logger,
    )
