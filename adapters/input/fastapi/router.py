from fastapi import APIRouter
from arclith.domain.ports.logger import Logger

from application.services.ingredient_service import IngredientService
from application.services.recipe_service import RecipeService
from application.services.tool_service import ToolService
from adapters.input.fastapi.ingredient_router import IngredientRouter
from adapters.input.fastapi.recipe_router import RecipeRouter
from adapters.input.fastapi.tool_router import ToolRouter


class Router:
    def __init__(
        self,
        ingredient_service: IngredientService,
        recipe_service: RecipeService,
        tool_service: ToolService,
        logger: Logger,
    ) -> None:
        self.router = APIRouter()

        self.router.include_router(IngredientRouter(ingredient_service, logger).router)
        self.router.include_router(RecipeRouter(recipe_service, logger).router)
        self.router.include_router(ToolRouter(tool_service, logger).router)
