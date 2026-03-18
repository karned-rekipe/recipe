from fastapi import FastAPI

from arclith import Arclith
from adapters.input.fastapi.ingredient_router import IngredientRouter
from adapters.input.fastapi.recipe_router import RecipeRouter
from adapters.input.fastapi.tool_router import ToolRouter
from infrastructure.ingredient_container import build_ingredient_service
from infrastructure.recipe_container import build_recipe_service
from infrastructure.tool_container import build_tool_service


def register_routers(app: FastAPI, arclith: Arclith) -> None:
    ingredient_service, logger = build_ingredient_service(arclith)
    recipe_service, _ = build_recipe_service(arclith)
    tool_service, _ = build_tool_service(arclith)
    app.include_router(IngredientRouter(ingredient_service, logger).router)
    app.include_router(RecipeRouter(recipe_service, logger).router)
    app.include_router(ToolRouter(tool_service, logger).router)
