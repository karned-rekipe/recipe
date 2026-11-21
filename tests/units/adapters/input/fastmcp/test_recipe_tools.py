import json
from unittest.mock import AsyncMock, patch

import fastmcp
import pytest

from adapters.input.fastmcp.tools import AdminMCP, RecipeMCP
from adapters.output.memory.repositories.equipment_repository import InMemoryEquipmentRepository
from adapters.output.memory.repositories.ingredient_repository import InMemoryIngredientRepository
from application.services.recipe_service import RecipeService
from domain.models.equipment import Equipment
from domain.models.ingredient import Ingredient
from uuid6 import UUID

INGREDIENT_UUID = "01951234-5678-7abc-def0-000000000101"
INGREDIENT_2_UUID = "01951234-5678-7abc-def0-000000000103"
EQUIPMENT_UUID = "01951234-5678-7abc-def0-000000000102"
EQUIPMENT_2_UUID = "01951234-5678-7abc-def0-000000000104"


def _payload(**kwargs) -> dict:
    payload = {
        "name": "Farine",
        "description": "Recette de base",
        "servings": 4,
        "ingredients": [{
            "ingredient_uuid": INGREDIENT_UUID,
            "quantity": 500,
            "unit": "g",
        }],
        "equipment": [{"equipment_uuid": EQUIPMENT_UUID, "quantity": 1}],
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
def ingredient_repo():
    repository = InMemoryIngredientRepository()
    ingredients = [
        Ingredient(uuid=UUID(INGREDIENT_UUID), name="Farine de ble", unit="g"),
        Ingredient(uuid=UUID(INGREDIENT_2_UUID), name="Farine T80", unit="g"),
    ]
    for ingredient in ingredients:
        repository._store[ingredient.uuid] = ingredient
    return repository


@pytest.fixture
def equipment_repo():
    repository = InMemoryEquipmentRepository()
    equipment_items = [
        Equipment(uuid=UUID(EQUIPMENT_UUID), name="Saladier"),
        Equipment(uuid=UUID(EQUIPMENT_2_UUID), name="Robot"),
    ]
    for equipment in equipment_items:
        repository._store[equipment.uuid] = equipment
    return repository


@pytest.fixture
def service(repo, ingredient_repo, equipment_repo, logger):
    return RecipeService(
        repo,
        logger,
        ingredient_repository=ingredient_repo,
        equipment_repository=equipment_repo,
    )


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
                equipment=[{"equipment_uuid": EQUIPMENT_2_UUID, "quantity": 1}],
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
                    "ingredient_uuid": INGREDIENT_2_UUID,
                    "quantity": 450,
                    "unit": "g",
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


async def test_list_filters_recipes_without_main_image(client):
    await client.call_tool("create_recipe", {"payload": _payload(name="Sans image")})
    await client.call_tool(
        "create_recipe",
        {"payload": _payload(name="Image vide", main_image="   ")},
    )
    await client.call_tool(
        "create_recipe",
        {"payload": _payload(name="Avec image", main_image="https://example.com/recipe.jpg")},
    )

    result = await client.call_tool("list_recipes", {"has_main_image": False})

    assert {item["name"] for item in _data(result)} == {"Sans image", "Image vide"}


async def test_list_combines_main_image_filter_and_pagination(client):
    await client.call_tool("create_recipe", {"payload": _payload(name="A illustrer 1")})
    await client.call_tool("create_recipe", {"payload": _payload(name="A illustrer 2")})
    await client.call_tool(
        "create_recipe",
        {"payload": _payload(name="Deja illustree", main_image="https://example.com/recipe.jpg")},
    )

    result = await client.call_tool(
        "list_recipes",
        {"has_main_image": False, "offset": 1, "limit": 1},
    )

    items = _data(result)
    assert len(items) == 1
    assert items[0]["name"] == "A illustrer 2"


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
