import fastmcp

from arclith import Arclith
from adapters.input.fastmcp.ingredient_tools import IngredientMCP
from adapters.input.fastmcp.recipe_tools import RecipeMCP
from adapters.input.fastmcp.tool_tools import ToolMCP
from application.services.recipe_service import RecipeService
from infrastructure.ingredient_container import build_ingredient_service


def register_tools(mcp: fastmcp.FastMCP, arclith: Arclith) -> None:
    service, logger = build_ingredient_service(arclith)
    IngredientMCP(service, logger, mcp)
    RecipeMCP(RecipeService, logger, mcp)
    ToolMCP(service, logger, mcp)
