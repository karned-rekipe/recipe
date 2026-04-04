from adapters.input.fastapi.routers import AdminRouter, IngredientRouter, RecipeRouter
from arclith import Arclith
from fastapi import FastAPI
from infrastructure.containers.ingredient_container import build_ingredient_service
from infrastructure.containers.recipe_container import build_recipe_service
from infrastructure.purge_registry import purge_registry


def register_routers(app: FastAPI, arclith: Arclith) -> None:
    recipe_service, logger = build_recipe_service(arclith)
    purge_registry.register("recipes", recipe_service.purge)
    app.include_router(RecipeRouter(recipe_service, logger).router)

    ingredient_service, ingredient_logger = build_ingredient_service(arclith)
    purge_registry.register("ingredients", ingredient_service.purge)
    app.include_router(IngredientRouter(ingredient_service, ingredient_logger).router)

    app.include_router(AdminRouter(purge_registry).router)
