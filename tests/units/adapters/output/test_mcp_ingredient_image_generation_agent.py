from types import SimpleNamespace

import pytest

from adapters.output.ingredient_agent import MCPIngredientImageGenerationAgent


async def test_agent_calls_internal_mcp_tool(monkeypatch):
    captured: dict = {}

    class _Client:
        def __init__(self, transport, *, timeout):
            captured["url"] = transport.url
            captured["headers"] = transport.headers
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
                        "run_uuid": "run-1",
                        "ingredient_uuid": "ingredient-1",
                        "suggestion_uuid": "suggestion-1",
                        "status": "success",
                        "completeness_score": 25,
                        "missing_fields": ["media_profile"],
                        "proposed_fields": ["media_profile"],
                    }
                },
            )

    monkeypatch.setattr(
        "adapters.output.ingredient_agent.mcp_ingredient_image_generation_agent.fastmcp.Client",
        _Client,
    )
    agent = MCPIngredientImageGenerationAgent(
        "http://ingredient-agent:8034/mcp",
        timeout_seconds=42,
        tenant_uri="foyer-demo",
    )

    result = await agent.generate(ingredient_uuid="ingredient-1")

    assert result.suggestion_uuid == "suggestion-1"
    assert captured == {
        "url": "http://ingredient-agent:8034/mcp",
        "headers": {"X-Tenant-URI": "foyer-demo"},
        "client_timeout": 42,
        "name": "generate_ingredient_image",
        "args": {"ingredient_uuid": "ingredient-1"},
        "call_timeout": 42,
    }


async def test_agent_rejects_non_image_result(monkeypatch):
    class _Client:
        def __init__(self, transport, *, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def call_tool(self, name, args, *, timeout):
            return SimpleNamespace(
                data={
                    "run_uuid": "run-1",
                    "ingredient_uuid": "ingredient-1",
                    "suggestion_uuid": "suggestion-1",
                    "status": "success",
                    "completeness_score": 25,
                    "missing_fields": [],
                    "proposed_fields": ["nutrition_profile"],
                },
                content=[],
                structured_content=None,
            )

    monkeypatch.setattr(
        "adapters.output.ingredient_agent.mcp_ingredient_image_generation_agent.fastmcp.Client",
        _Client,
    )
    agent = MCPIngredientImageGenerationAgent("http://ingredient-agent:8034/mcp")

    with pytest.raises(RuntimeError, match="invalid result"):
        await agent.generate(ingredient_uuid="ingredient-1")


def test_agent_rejects_non_http_url():
    with pytest.raises(ValueError, match="http or https"):
        MCPIngredientImageGenerationAgent("file:///tmp/agent.sock")
