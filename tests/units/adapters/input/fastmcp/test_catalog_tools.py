import json
from unittest.mock import AsyncMock, patch

import fastmcp
import pytest
from adapters.input.fastmcp.tools import EquipmentMCP, IngredientGroupMCP, IngredientMCP, IngredientRayonMCP, TagMCP
from adapters.output.memory.repositories.equipment_repository import InMemoryEquipmentRepository
from adapters.output.memory.repositories.ingredient_enrichment_suggestion_repository import (
    InMemoryIngredientEnrichmentSuggestionRepository,
)
from adapters.output.memory.repositories.ingredient_group_repository import InMemoryIngredientGroupRepository
from adapters.output.memory.repositories.ingredient_rayon_repository import InMemoryIngredientRayonRepository
from adapters.output.memory.repositories.ingredient_repository import InMemoryIngredientRepository
from adapters.output.memory.repositories.tag_repository import InMemoryTagRepository
from application.services.equipment_service import EquipmentService
from application.services.ingredient_enrichment_suggestion_service import IngredientEnrichmentSuggestionService
from application.services.ingredient_group_service import IngredientGroupService
from application.services.ingredient_rayon_service import IngredientRayonService
from application.services.ingredient_service import IngredientService
from application.services.tag_service import TagService


class FakeRecipeService:
    async def is_ingredient_used(self, uuid) -> bool:
        return False

    async def is_equipment_used(self, uuid) -> bool:
        return False

    async def is_tag_used(self, uuid) -> bool:
        return False

    async def find_page_filtered_hydrated(self, **kwargs) -> tuple[list, int]:
        return [], 0

    async def replace_equipment_reference(self, source_uuid, target_uuid) -> int:
        return 1

    async def replace_ingredient_reference(self, source_uuid, target_uuid) -> int:
        return 1


@pytest.fixture
def mcp_app() -> fastmcp.FastMCP:
    return fastmcp.FastMCP("test")


@pytest.fixture
async def client(logger, mcp_app: fastmcp.FastMCP):
    recipe_service = FakeRecipeService()
    with (
        patch("adapters.input.fastmcp.tools.equipment_tools.inject_tenant_uri", new=AsyncMock()),
        patch("adapters.input.fastmcp.tools.tag_tools.inject_tenant_uri", new=AsyncMock()),
        patch("adapters.input.fastmcp.tools.ingredient_setting_tools.inject_tenant_uri", new=AsyncMock()),
        patch("adapters.input.fastmcp.tools.ingredient_tools.inject_tenant_uri", new=AsyncMock()),
    ):
        EquipmentMCP(
            EquipmentService(InMemoryEquipmentRepository(), logger),
            logger,
            mcp_app,
            recipe_service,
        )
        TagMCP(TagService(InMemoryTagRepository(), logger), logger, mcp_app, recipe_service)
        ingredient_repository = InMemoryIngredientRepository()
        ingredient_service = IngredientService(ingredient_repository, logger)
        suggestion_service = IngredientEnrichmentSuggestionService(
            InMemoryIngredientEnrichmentSuggestionRepository(),
            ingredient_repository,
            logger,
        )
        IngredientMCP(
            ingredient_service,
            logger,
            mcp_app,
            recipe_service,
            suggestion_service,
        )
        IngredientGroupMCP(
            IngredientGroupService(InMemoryIngredientGroupRepository(), logger),
            logger,
            mcp_app,
        )
        IngredientRayonMCP(
            IngredientRayonService(InMemoryIngredientRayonRepository(), logger),
            logger,
            mcp_app,
        )
        async with fastmcp.Client(mcp_app) as fastmcp_client:
            yield fastmcp_client


def _data(result) -> dict | list | None:
    if not result.content:
        return result.data
    return json.loads(result.content[0].text)


async def test_equipment_mcp_crud_and_duplicates(client) -> None:
    created = _data(await client.call_tool("create_equipment", {"name": "Four", "description": "Chaleur tournante"}))
    duplicate = _data(await client.call_tool("create_equipment", {"name": "four"}))

    fetched = _data(await client.call_tool("get_equipment", {"uuid": created["uuid"]}))
    listed = _data(await client.call_tool("list_equipment", {"name": "four"}))
    duplicated = _data(await client.call_tool("duplicate_equipment", {"uuid": created["uuid"]}))
    duplicate_groups = _data(await client.call_tool("list_equipment_duplicates", {}))

    await client.call_tool("update_equipment", {"uuid": created["uuid"], "name": "Four vapeur"})
    updated = _data(await client.call_tool("get_equipment", {"uuid": created["uuid"]}))
    recipes = _data(await client.call_tool("list_recipes_for_equipment", {"uuid": created["uuid"]}))
    merge_result = _data(
        await client.call_tool(
            "merge_equipment_duplicates",
            {"target_uuid": created["uuid"], "duplicate_uuids": [duplicate["uuid"]]},
        )
    )
    await client.call_tool("delete_equipment", {"uuid": duplicated["uuid"]})

    assert fetched["name"] == "Four"
    assert len(listed) >= 2
    assert duplicate_groups
    assert updated["name"] == "Four vapeur"
    assert recipes == []
    assert merge_result["deleted_count"] == 1


async def test_tag_mcp_crud(client) -> None:
    created = _data(await client.call_tool("create_tag", {"name": "Express", "category": "other", "color": "#333333"}))

    fetched = _data(await client.call_tool("get_tag", {"uuid": created["uuid"]}))
    listed = _data(await client.call_tool("list_tags", {"name": "press"}))
    recipes = _data(await client.call_tool("list_recipes_for_tag", {"uuid": created["uuid"]}))
    await client.call_tool("delete_tag", {"uuid": created["uuid"]})
    missing = _data(await client.call_tool("get_tag", {"uuid": created["uuid"]}))

    assert fetched["name"] == "Express"
    assert len(listed) == 1
    assert recipes == []
    assert missing is None


async def test_ingredient_group_and_rayon_mcp_crud(client) -> None:
    group = _data(await client.call_tool("create_ingredient_group", {"name": "Legumes"}))
    rayon = _data(await client.call_tool("create_ingredient_rayon", {"name": "Frais"}))

    groups = _data(await client.call_tool("list_ingredient_groups", {"name": "leg"}))
    rayons = _data(await client.call_tool("list_ingredient_rayons", {"name": "fra"}))
    await client.call_tool("delete_ingredient_group", {"uuid": group["uuid"]})
    await client.call_tool("delete_ingredient_rayon", {"uuid": rayon["uuid"]})

    assert groups[0]["name"] == "Legumes"
    assert rayons[0]["name"] == "Frais"


async def test_ingredient_mcp_v5_tools(client) -> None:
    created = _data(
        await client.call_tool(
            "create_ingredient",
            {"name": "Tomate", "unit": "g", "quantity": 100, "season_months": {"7": 3, "8": 3}},
        )
    )
    duplicate = _data(await client.call_tool("create_ingredient", {"name": "tomate", "unit": "g"}))

    fetched = _data(await client.call_tool("get_ingredient", {"uuid": created["uuid"]}))
    listed = _data(await client.call_tool("list_ingredients", {"name": "tom"}))
    units = _data(await client.call_tool("list_units", {}))
    converted = _data(
        await client.call_tool(
            "convert_ingredient_unit",
            {"ingredient_uuid": created["uuid"], "quantity": 1.5, "from_unit": "kg", "to_unit": "g"},
        )
    )
    cloned = _data(await client.call_tool("duplicate_ingredient", {"uuid": created["uuid"]}))
    recipes = _data(await client.call_tool("list_recipes_for_ingredient", {"uuid": created["uuid"]}))
    duplicate_groups = _data(await client.call_tool("list_ingredient_duplicates", {}))
    merge_result = _data(
        await client.call_tool(
            "merge_ingredient_duplicates",
            {"target_uuid": created["uuid"], "duplicate_uuids": [duplicate["uuid"]]},
        )
    )
    suggestion = _data(
        await client.call_tool(
            "create_ingredient_enrichment_suggestion",
            {
                "ingredient_uuid": created["uuid"],
                "run_uuid": "019ab73e-ff10-741c-9f01-51414e165ed7",
                "proposed_patch": {"media_profile": {"image_status": "missing"}},
                "field_confidences": {"media_profile": 0.1},
                "field_sources": {"media_profile": "ai"},
                "reasoning_summary": "test",
            },
        )
    )
    suggestions = _data(await client.call_tool("list_ingredient_enrichment_suggestions", {"ingredient_uuid": created["uuid"]}))
    applied = _data(
        await client.call_tool(
            "apply_ingredient_enrichment_suggestion",
            {"ingredient_uuid": created["uuid"], "suggestion_uuid": suggestion["uuid"], "fields": ["media_profile"]},
        )
    )
    rejected_suggestion = _data(
        await client.call_tool(
            "create_ingredient_enrichment_suggestion",
            {
                "ingredient_uuid": created["uuid"],
                "run_uuid": "019ab73e-ff10-741c-9f01-51414e165ed7",
                "proposed_patch": {"nutrition_profile": {"nutri_score": "unknown"}},
                "reasoning_summary": "test",
            },
        )
    )
    rejected = _data(
        await client.call_tool(
            "reject_ingredient_enrichment_suggestion",
            {
                "ingredient_uuid": created["uuid"],
                "suggestion_uuid": rejected_suggestion["uuid"],
                "fields": ["nutrition_profile"],
            },
        )
    )
    await client.call_tool("delete_ingredient", {"uuid": cloned["uuid"]})

    assert fetched["name"] == "Tomate"
    assert len(listed) >= 2
    assert any(unit["code"] == "kg" for unit in units)
    assert converted["converted_quantity"] == 1500
    assert recipes == []
    assert duplicate_groups
    assert merge_result["deleted_count"] == 1
    assert suggestions[0]["uuid"] == suggestion["uuid"]
    assert applied["status"] == "applied"
    assert rejected["status"] == "rejected"
