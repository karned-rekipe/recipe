from types import SimpleNamespace

import pytest

from adapters.output.recipe_agent import MCPRecipeAIEnrichmentAgent


async def test_agent_calls_internal_mcp_tool(monkeypatch):
    captured: dict = {}

    class _Client:
        def __init__(self, transport, *, timeout):
            captured["url"] = transport.url
            captured["client_timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def call_tool(self, name, args, *, timeout):
            captured.update(name=name, args=args, call_timeout=timeout)
            return SimpleNamespace(
                data=None,
                content=[],
                structured_content={
                    "result": {
                        "recipe_uuid": "recipe-1",
                        "recipe_name": "Soupe",
                        "formatted_response": "Recette enrichie",
                        "updated": True,
                        "image_generated": False,
                        "warnings": [],
                    }
                },
            )

    monkeypatch.setattr(
        "adapters.output.recipe_agent.mcp_recipe_ai_enrichment_agent.fastmcp.Client",
        _Client,
    )
    agent = MCPRecipeAIEnrichmentAgent("http://recipe-agent:8004/mcp", timeout_seconds=42)

    result = await agent.enrich(recipe_uuid="recipe-1", generate_image=False)

    assert result.updated is True
    assert captured == {
        "url": "http://recipe-agent:8004/mcp",
        "client_timeout": 42,
        "name": "ai_enrich_recipe",
        "args": {"recipe_uuid": "recipe-1", "generate_image": False},
        "call_timeout": 42,
    }


def test_agent_rejects_non_http_url():
    with pytest.raises(ValueError, match="http or https"):
        MCPRecipeAIEnrichmentAgent("file:///tmp/agent.sock")
