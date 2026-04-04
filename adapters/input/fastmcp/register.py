"""MCP tools registration."""

import fastmcp
from adapters.input.fastmcp.tools import AdminMCP, IngredientMCP, RecipeMCP
from arclith import Arclith
from infrastructure.containers.ingredient_container import build_ingredient_service
from infrastructure.containers.recipe_container import build_recipe_service
from infrastructure.purge_registry import purge_registry


def register_tools(mcp: fastmcp.FastMCP, arclith: Arclith) -> None:
    """Register all MCP tools."""
    recipe_service, logger = build_recipe_service(arclith)
    purge_registry.register("recipes", recipe_service.purge)
    RecipeMCP(recipe_service, logger, mcp)

    ingredient_service, ingredient_logger = build_ingredient_service(arclith)
    purge_registry.register("ingredients", ingredient_service.purge)
    IngredientMCP(ingredient_service, ingredient_logger, mcp)

    AdminMCP(purge_registry, logger, mcp)

