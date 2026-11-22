from __future__ import annotations

import os

from adapters.output.recipe_agent import MCPRecipeAIEnrichmentAgent
from domain.ports.output.recipe_ai_enrichment_agent import RecipeAIEnrichmentAgent


def build_recipe_ai_enrichment_agent() -> RecipeAIEnrichmentAgent:
    return MCPRecipeAIEnrichmentAgent(
        os.getenv("RECIPE_AGENT_MCP_URL", "http://127.0.0.1:8004/mcp"),
        timeout_seconds=float(os.getenv("RECIPE_AGENT_MCP_TIMEOUT_SECONDS", "300")),
    )
