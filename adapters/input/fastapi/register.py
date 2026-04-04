from adapters.input.fastapi.routers import AdminRouter, RecipeRouter
from arclith import Arclith
from fastapi import FastAPI
from infrastructure.containers.recipe_container import build_recipe_service
from infrastructure.purge_registry import purge_registry


def register_routers(app: FastAPI, arclith: Arclith) -> None:
    service, logger = build_recipe_service(arclith)
    purge_registry.register("recipes", service.purge)
    app.include_router(RecipeRouter(service, logger).router)
    app.include_router(AdminRouter(purge_registry).router)
