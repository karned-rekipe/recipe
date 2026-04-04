"""MCP prompts."""

import fastmcp

from arclith import Arclith
from adapters.input.fastmcp.prompts.recipe_prompts import RecipePrompts
from infrastructure.containers.recipe_container import build_recipe_service

__all__ = ["RecipePrompts"]


def register_prompts(mcp: fastmcp.FastMCP, arclith: Arclith) -> None:
    service, logger = build_recipe_service(arclith)
    RecipePrompts(service, logger, mcp)
