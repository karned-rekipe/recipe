import fastmcp
from arclith import Arclith

from adapters.input.fastmcp.ingredient_tools import IngredientMCP
from adapters.input.fastmcp.recipe_ingredient_tools import RecipeIngredientMCP
from adapters.input.fastmcp.recipe_tools import RecipeMCP
from adapters.input.fastmcp.recipe_ustensil_tools import RecipeUstensilMCP
from adapters.input.fastmcp.step_tools import StepMCP
from adapters.input.fastmcp.ustensil_tools import UstensilMCP
from infrastructure.ingredient_container import build_ingredient_service
from infrastructure.recipe_container import build_recipe_service
from infrastructure.step_container import build_step_service
from infrastructure.ustensil_container import build_ustensil_service


def register_tools(mcp: fastmcp.FastMCP, arclith: Arclith) -> None:
    ingredient_service, logger = build_ingredient_service(arclith)
    recipe_service, _ = build_recipe_service(arclith)
    ustensil_service, _ = build_ustensil_service(arclith)
    step_service, _ = build_step_service(arclith)
    IngredientMCP(ingredient_service, logger, mcp)
    UstensilMCP(ustensil_service, logger, mcp)
    StepMCP(step_service, logger, mcp)
    RecipeMCP(recipe_service, logger, mcp)
    RecipeIngredientMCP(recipe_service, logger, mcp)
    RecipeUstensilMCP(recipe_service, logger, mcp)
