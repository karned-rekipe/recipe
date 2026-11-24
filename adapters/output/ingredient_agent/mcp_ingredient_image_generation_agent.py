from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit

import fastmcp
from fastmcp.client.transports import StreamableHttpTransport
from pydantic import BaseModel, ValidationError

from domain.models.ingredient_image_generation import IngredientImageGeneration
from domain.ports.output.ingredient_image_generation_agent import IngredientImageGenerationAgent


def _plain_data(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _plain_data(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {key: _plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_data(item) for item in value]
    return value


class MCPIngredientImageGenerationAgent(IngredientImageGenerationAgent):
    def __init__(
        self,
        mcp_url: str,
        timeout_seconds: float = 180.0,
        tenant_uri: str | None = None,
    ) -> None:
        if urlsplit(mcp_url).scheme not in {"http", "https"}:
            raise ValueError("Ingredient agent MCP URL must use http or https")
        self._mcp_url = mcp_url
        self._timeout_seconds = timeout_seconds
        self._tenant_uri = tenant_uri

    async def generate(self, *, ingredient_uuid: str) -> IngredientImageGeneration:
        headers = {"X-Tenant-URI": self._tenant_uri} if self._tenant_uri else None
        transport = StreamableHttpTransport(self._mcp_url, headers=headers)
        try:
            async with fastmcp.Client(transport, timeout=self._timeout_seconds) as client:
                result = await client.call_tool(
                    "generate_ingredient_image",
                    {"ingredient_uuid": ingredient_uuid},
                    timeout=self._timeout_seconds,
                )
        except Exception as exc:
            raise RuntimeError(
                "L’agent de génération d’image des ingrédients est indisponible"
            ) from exc

        payload: Any = result.data
        if result.structured_content:
            payload = result.structured_content.get("result", result.structured_content)
        elif result.content:
            text = getattr(result.content[0], "text", None)
            if text:
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise RuntimeError("Ingredient image agent returned invalid JSON") from exc

        try:
            return IngredientImageGeneration.model_validate(_plain_data(payload))
        except ValidationError as exc:
            raise RuntimeError("Ingredient image agent returned an invalid result") from exc
