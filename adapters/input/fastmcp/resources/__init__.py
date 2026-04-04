"""MCP resources."""

import fastmcp

from arclith import Arclith
from adapters.input.fastmcp.resources.recipe_resources import RecipeResources
from infrastructure.containers.recipe_container import build_recipe_service

__all__ = ["RecipeResources"]


def register_resources(mcp: fastmcp.FastMCP, arclith: Arclith) -> None:
    service, logger = build_recipe_service(arclith)
    RecipeResources(service, logger, mcp)
