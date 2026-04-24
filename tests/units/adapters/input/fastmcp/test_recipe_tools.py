import json
from unittest.mock import AsyncMock, patch

import fastmcp
import pytest

from adapters.input.fastmcp.tools import AdminMCP, RecipeMCP
from application.services.recipe_service import RecipeService


def _payload(**kwargs) -> dict:
    payload = {
        "name": "Farine",
        "description": "Recette de base",
        "servings": 4,
        "ingredients": [{
            "name": "Farine de ble",
            "quantity": 500,
            "unit": "g",
            "season_months": {},
        }],
        "equipment": [{"name": "Saladier", "quantity": 1}],
        "steps": [{
            "name": "Melanger",
            "description": "Melanger les ingredients.",
            "rank": 1,
            "secondary_images": [],
        }],
        "sources": [],
        "secondary_images": [],
    }
    payload.update(kwargs)
    return payload


@pytest.fixture
def mcp_app():
    return fastmcp.FastMCP("test")


@pytest.fixture
def service(repo, logger):
    return RecipeService(repo, logger)


@pytest.fixture
async def client(service, logger, mcp_app):
    with patch("adapters.input.fastmcp.tools.recipe_tools.inject_tenant_uri", new=AsyncMock()):
        with patch("adapters.input.fastmcp.tools.recipe_tools.require_auth_mcp", new=AsyncMock(return_value={"sub": "test-user"})):
            with patch("adapters.input.fastmcp.tools.admin_tools.require_auth_mcp", new=AsyncMock(return_value={"sub": "test-user"})):
                from infrastructure.purge_registry import PurgeRegistry
                registry = PurgeRegistry()
                registry.register("recipes", service.purge)
                RecipeMCP(service, logger, mcp_app)
                AdminMCP(registry, logger, mcp_app)
                async with fastmcp.Client(mcp_app) as c:
                    yield c


def _data(result) -> dict | list | None:
    if not result.content:
        return result.data
    return json.loads(result.content[0].text)


@pytest.fixture
async def created_uuid(client) -> str:
    result = await client.call_tool("create_recipe", {"payload": _payload()})
    data = _data(result)
    assert isinstance(data, dict)
    return data["uuid"]


async def test_create_returns_complete_recipe(client):
    result = await client.call_tool(
        "create_recipe",
        {
            "payload": _payload(
                legacy_id=42,
                favorite=True,
                quality_status="text_only",
                migration_metadata={"source_table": "mkg_recipe"},
            )
        },
    )
    data = _data(result)
    assert data["name"] == "Farine"
    assert data["servings"] == 4
    assert data["ingredients"][0]["name"] == "Farine de ble"
    assert data["equipment"][0]["name"] == "Saladier"
    assert data["steps"][0]["name"] == "Melanger"
    assert data["legacy_id"] == 42
    assert data["favorite"] is True
    assert data["quality_status"] == "text_only"
    assert data["migration_metadata"] == {"source_table": "mkg_recipe"}


async def test_get_found(client, created_uuid):
    result = await client.call_tool("get_recipe", {"uuid": created_uuid})
    assert _data(result)["name"] == "Farine"


async def test_get_not_found_returns_none(client):
    result = await client.call_tool("get_recipe", {"uuid": "01951234-5678-7abc-def0-000000000000"})
    assert _data(result) is None


async def test_update_changes_full_aggregate(client, created_uuid):
    await client.call_tool(
        "update_recipe",
        {
            "uuid": created_uuid,
            "payload": _payload(
                name="Farine T55",
                equipment=[{"name": "Robot", "quantity": 1}],
            ),
        },
    )
    result = await client.call_tool("get_recipe", {"uuid": created_uuid})
    data = _data(result)
    assert data["name"] == "Farine T55"
    assert data["equipment"][0]["name"] == "Robot"


async def test_patch_replaces_provided_sections_only(client, created_uuid):
    await client.call_tool(
        "patch_recipe",
        {
            "uuid": created_uuid,
            "payload": {
                "ingredients": [{
                    "name": "Farine T80",
                    "quantity": 450,
                    "unit": "g",
                    "season_months": {},
                }],
            },
        },
    )
    result = await client.call_tool("get_recipe", {"uuid": created_uuid})
    data = _data(result)
    assert data["name"] == "Farine"
    assert data["ingredients"][0]["name"] == "Farine T80"
    assert data["steps"][0]["name"] == "Melanger"


async def test_patch_updates_migration_metadata(client, created_uuid):
    await client.call_tool(
        "patch_recipe",
        {
            "uuid": created_uuid,
            "payload": {
                "quality_status": "validated",
                "migration_metadata": {"source_table": "mkg_recipe", "qc_passed": True},
            },
        },
    )
    result = await client.call_tool("get_recipe", {"uuid": created_uuid})
    data = _data(result)

    assert data["quality_status"] == "validated"
    assert data["migration_metadata"] == {"source_table": "mkg_recipe", "qc_passed": True}


async def test_delete_hides_recipe(client, created_uuid):
    await client.call_tool("delete_recipe", {"uuid": created_uuid})
    result = await client.call_tool("get_recipe", {"uuid": created_uuid})
    assert _data(result) is None


async def test_list_all(client):
    await client.call_tool("create_recipe", {"payload": _payload(name="Farine")})
    await client.call_tool("create_recipe", {"payload": _payload(name="Sel")})
    result = await client.call_tool("list_recipes", {})
    assert len(_data(result)) == 2


async def test_list_filtered(client):
    await client.call_tool("create_recipe", {"payload": _payload(name="Farine de ble")})
    await client.call_tool("create_recipe", {"payload": _payload(name="Sel fin")})
    result = await client.call_tool("list_recipes", {"name": "farine"})
    items = _data(result)
    assert len(items) == 1
    assert items[0]["name"] == "Farine de ble"


async def test_duplicate_returns_new_uuid(client, created_uuid):
    result = await client.call_tool("duplicate_recipe", {"uuid": created_uuid})
    data = _data(result)
    assert data["uuid"] != created_uuid
    assert data["ingredients"][0]["name"] == "Farine de ble"


async def test_purge_returns_count(client):
    result = await client.call_tool("purge_all", {})
    data = _data(result)
    assert "purged" in data
    assert "total" in data
