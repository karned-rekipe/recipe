from pathlib import Path

from arclith import Arclith

from adapters.input.fastmcp.prompts import IngredientPrompts
from adapters.input.fastmcp.register import register_tools
from adapters.input.fastmcp.resources import IngredientResources
from infrastructure.container import build_ingredient_service

arclith = Arclith(Path(__file__).parent / "config.yaml")
mcp = arclith.fastmcp("Rekipe")
register_tools(mcp, arclith)
ingredient_service, logger = build_ingredient_service(arclith)
IngredientResources(ingredient_service, logger, mcp)
IngredientPrompts(ingredient_service, logger, mcp)

if __name__ == "__main__":
    arclith.run_mcp_http(mcp)
