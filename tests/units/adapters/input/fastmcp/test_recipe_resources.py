import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

import fastmcp
import pytest

from adapters.input.fastmcp.resources import RecipeResources
from application.services.recipe_service import RecipeService
from domain.models.recipe import Recipe


@pytest.fixture
def mcp_app():
    return fastmcp.FastMCP("test")


@pytest.fixture
def service(repo, logger):
    return RecipeService(repo, logger)


@pytest.fixture
async def client(service, logger, mcp_app):
    with patch("adapters.input.fastmcp.resources.recipe_resources.inject_tenant_uri", new=AsyncMock()):
        RecipeResources(service, logger, mcp_app)
        async with fastmcp.Client(mcp_app) as c:
            yield c


def _json(result: list) -> list | dict | None:
    return json.loads(result[0].text)


# --- recipes://sample ---

async def test_sample_empty(client):
    result = await client.read_resource("recipes://sample")
    assert _json(result) == []


async def test_sample_returns_at_most_5(client, service):
    for i in range(8):
        await service.create(Recipe(name=f"Recipe {i:02d}"))
    result = await client.read_resource("recipes://sample")
    assert len(_json(result)) <= 5


async def test_sample_is_oldest_first(client, service):
    for i in range(6):
        await service.create(Recipe(name=f"Item {i:02d}"))
    result = await client.read_resource("recipes://sample")
    data = _json(result)
    assert len(data) == 5
    dates = [datetime.fromisoformat(d["created_at"]) for d in data]
    assert dates == sorted(dates)


# --- recipes://recent ---

async def test_recent_empty(client):
    result = await client.read_resource("recipes://recent")
    assert _json(result) == []


async def test_recent_returns_at_most_10(client, service):
    for i in range(12):
        await service.create(Recipe(name=f"Recipe {i:02d}"))
    result = await client.read_resource("recipes://recent")
    assert len(_json(result)) <= 10


async def test_recent_is_newest_first(client, service):
    for i in range(12):
        await service.create(Recipe(name=f"Item {i:02d}"))
    result = await client.read_resource("recipes://recent")
    data = _json(result)
    assert len(data) == 10
    dates = [datetime.fromisoformat(d["created_at"]) for d in data]
    assert dates == sorted(dates, reverse=True)


# --- recipe://{uuid} ---

async def test_get_resource_found(client, service):
    item = await service.create(Recipe(name="Sel"))
    result = await client.read_resource(f"recipe://{item.uuid}")
    data = _json(result)
    assert data is not None
    assert data["name"] == "Sel"


async def test_get_resource_not_found_returns_null(client):
    result = await client.read_resource("recipe://01951234-5678-7abc-def0-000000000000")
    assert _json(result) is None

