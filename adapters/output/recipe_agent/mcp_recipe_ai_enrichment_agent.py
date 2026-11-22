from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit

import fastmcp
from fastmcp.client.transports import StreamableHttpTransport
from pydantic import BaseModel, ValidationError

from domain.models.recipe_ai_enrichment import RecipeAIEnrichment
from domain.ports.output.recipe_ai_enrichment_agent import RecipeAIEnrichmentAgent


def _plain_data(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _plain_data(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {key: _plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_data(item) for item in value]
    return value


class MCPRecipeAIEnrichmentAgent(RecipeAIEnrichmentAgent):
    def __init__(self, mcp_url: str, timeout_seconds: float = 300.0) -> None:
        if urlsplit(mcp_url).scheme not in {"http", "https"}:
            raise ValueError("Recipe agent MCP URL must use http or https")
        self._mcp_url = mcp_url
        self._timeout_seconds = timeout_seconds

    async def enrich(
        self,
        *,
        recipe_uuid: str,
        generate_image: bool = True,
    ) -> RecipeAIEnrichment:
        transport = StreamableHttpTransport(self._mcp_url)
        try:
            async with fastmcp.Client(transport, timeout=self._timeout_seconds) as client:
                result = await client.call_tool(
                    "ai_enrich_recipe",
                    {
                        "recipe_uuid": recipe_uuid,
                        "generate_image": generate_image,
                    },
                    timeout=self._timeout_seconds,
                )
        except Exception as exc:
            raise RuntimeError("Recipe AI agent is unavailable") from exc

        payload: Any = result.data
        if result.structured_content:
            payload = result.structured_content.get("result", result.structured_content)
        elif result.content:
            text = getattr(result.content[0], "text", None)
            if text:
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise RuntimeError("Recipe AI agent returned invalid JSON") from exc

        try:
            return RecipeAIEnrichment.model_validate(_plain_data(payload))
        except ValidationError as exc:
            raise RuntimeError("Recipe AI agent returned an invalid enrichment result") from exc
