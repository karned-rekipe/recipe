from __future__ import annotations

import os

from adapters.output.ingredient_agent import MCPIngredientImageGenerationAgent
from domain.ports.output.ingredient_image_generation_agent import IngredientImageGenerationAgent


def build_ingredient_image_generation_agent() -> IngredientImageGenerationAgent:
    return MCPIngredientImageGenerationAgent(
        os.getenv(
            "INGREDIENT_ENRICHMENT_AGENT_MCP_URL",
            "http://127.0.0.1:8034/mcp",
        ),
        timeout_seconds=float(
            os.getenv("INGREDIENT_ENRICHMENT_AGENT_MCP_TIMEOUT_SECONDS", "180")
        ),
        tenant_uri=os.getenv("REKIPE_TENANT_URI"),
    )
