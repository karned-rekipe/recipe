from uuid6 import uuid7


async def test_create_ingredient(mcp, ingredient_mcp):
    result = await mcp.call_tool("create_ingredient", {"name": "Farine"})
    assert result.structured_content["name"] == "Farine"


async def test_create_ingredient_with_unit(mcp, ingredient_mcp):
    result = await mcp.call_tool("create_ingredient", {"name": "Eau", "unit": "ml"})
    assert result.structured_content["unit"] == "ml"


async def test_get_ingredient(mcp, ingredient_mcp):
    created = await mcp.call_tool("create_ingredient", {"name": "Sel"})
    uid = created.structured_content["uuid"]
    result = await mcp.call_tool("get_ingredient", {"uuid": uid})
    data = result.structured_content.get("result", result.structured_content)
    assert data["name"] == "Sel"


async def test_get_ingredient_not_found(mcp, ingredient_mcp):
    result = await mcp.call_tool("get_ingredient", {"uuid": str(uuid7())})
    assert result.structured_content is None or result.structured_content.get("result") is None


async def test_update_ingredient(mcp, ingredient_mcp):
    created = await mcp.call_tool("create_ingredient", {"name": "Farine"})
    uid = created.structured_content["uuid"]
    result = await mcp.call_tool("update_ingredient", {"uuid": uid, "name": "Farine complète"})
    assert result is not None


async def test_delete_ingredient(mcp, ingredient_mcp):
    created = await mcp.call_tool("create_ingredient", {"name": "Sel"})
    uid = created.structured_content["uuid"]
    await mcp.call_tool("delete_ingredient", {"uuid": uid})
    result = await mcp.call_tool("get_ingredient", {"uuid": uid})
    data = result.structured_content.get("result") if result.structured_content else None
    assert data is None or data.get("is_deleted")


async def test_list_ingredients(mcp, ingredient_mcp):
    await mcp.call_tool("create_ingredient", {"name": "Farine"})
    await mcp.call_tool("create_ingredient", {"name": "Sel"})
    result = await mcp.call_tool("list_ingredients", {})
    items = result.structured_content.get("result", result.structured_content)
    assert len(items) == 2


async def test_list_ingredients_with_filter(mcp, ingredient_mcp):
    await mcp.call_tool("create_ingredient", {"name": "Farine de blé"})
    await mcp.call_tool("create_ingredient", {"name": "Sel fin"})
    result = await mcp.call_tool("list_ingredients", {"name": "farine"})
    items = result.structured_content.get("result", result.structured_content)
    assert len(items) == 1


async def test_duplicate_ingredient(mcp, ingredient_mcp):
    created = await mcp.call_tool("create_ingredient", {"name": "Farine"})
    uid = created.structured_content["uuid"]
    result = await mcp.call_tool("duplicate_ingredient", {"uuid": uid})
    assert result.structured_content["uuid"] != uid
