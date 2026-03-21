from arclith import Arclith
from fastapi import FastAPI

from adapters.input.fastapi.ingredient_router import IngredientRouter
from adapters.input.fastapi.recipe_ingredient_router import RecipeIngredientRouter
from adapters.input.fastapi.recipe_router import RecipeRouter
from adapters.input.fastapi.recipe_ustensil_router import RecipeUstensilRouter
from adapters.input.fastapi.step_router import StepRouter
from adapters.input.fastapi.ustensil_router import UstensilRouter
from infrastructure.ingredient_container import build_ingredient_service
from infrastructure.recipe_container import build_recipe_service
from infrastructure.step_container import build_step_service
from infrastructure.ustensil_container import build_ustensil_service


def register_routers(app: FastAPI, arclith: Arclith) -> None:
    ingredient_service, logger = build_ingredient_service(arclith)
    recipe_service, _ = build_recipe_service(arclith)
    ustensil_service, _ = build_ustensil_service(arclith)
    step_service, _ = build_step_service(arclith)
    app.include_router(IngredientRouter(ingredient_service, logger).router)
    app.include_router(UstensilRouter(ustensil_service, logger).router)
    app.include_router(RecipeRouter(recipe_service, step_service, logger).router)
    app.include_router(RecipeIngredientRouter(recipe_service, logger).router)
    app.include_router(RecipeUstensilRouter(recipe_service, logger).router)
    app.include_router(StepRouter(step_service, logger).router)
