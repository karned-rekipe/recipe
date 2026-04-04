"""MCP tools registration."""

import fastmcp
from adapters.input.fastmcp.tools import AdminMCP, RecipeMCP
from arclith import Arclith
from infrastructure.containers.recipe_container import build_recipe_service
from infrastructure.purge_registry import purge_registry


def register_tools(mcp: fastmcp.FastMCP, arclith: Arclith) -> None:
    """Register all MCP tools."""
    service, logger = build_recipe_service(arclith)
    purge_registry.register("recipes", service.purge)
    RecipeMCP(service, logger, mcp)
    AdminMCP(purge_registry, logger, mcp)

