from __future__ import annotations

import os

from adapters.output.ingredient_agent import MCPIngredientEnrichmentAgent
from domain.ports.output.ingredient_enrichment_agent import IngredientEnrichmentAgent


def build_ingredient_enrichment_agent() -> IngredientEnrichmentAgent:
    return MCPIngredientEnrichmentAgent(
        os.getenv(
            "INGREDIENT_ENRICHMENT_AGENT_MCP_URL",
            "http://127.0.0.1:8034/mcp",
        ),
        timeout_seconds=float(
            os.getenv("INGREDIENT_ENRICHMENT_AGENT_MCP_TIMEOUT_SECONDS", "180")
        ),
        tenant_uri=os.getenv("REKIPE_TENANT_URI"),
    )
