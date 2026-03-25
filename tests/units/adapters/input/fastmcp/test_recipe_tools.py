from uuid6 import uuid7


async def test_create_recipe(mcp, recipe_mcp):
    result = await mcp.call_tool("create_recipe", {"name": "Pizza"})
    assert result.structured_content["name"] == "Pizza"


async def test_create_recipe_with_nutriscore(mcp, recipe_mcp):
    result = await mcp.call_tool("create_recipe", {"name": "Salade", "nutriscore": "A"})
    assert result.structured_content["nutriscore"] == "A"


async def test_get_recipe(mcp, recipe_mcp):
    created = await mcp.call_tool("create_recipe", {"name": "Pizza"})
    uid = created.structured_content["uuid"]
    result = await mcp.call_tool("get_recipe", {"uuid": uid})
    data = result.structured_content.get("result", result.structured_content)
    assert data["name"] == "Pizza"


async def test_get_recipe_not_found(mcp, recipe_mcp):
    result = await mcp.call_tool("get_recipe", {"uuid": str(uuid7())})
    assert result.structured_content is None or result.structured_content.get("result") is None


async def test_update_recipe(mcp, recipe_mcp):
    created = await mcp.call_tool("create_recipe", {"name": "Pizza"})
    uid = created.structured_content["uuid"]
    result = await mcp.call_tool("update_recipe", {"uuid": uid, "name": "Pizza Napolitaine"})
    assert result is not None


async def test_delete_recipe(mcp, recipe_mcp):
    created = await mcp.call_tool("create_recipe", {"name": "Pizza"})
    uid = created.structured_content["uuid"]
    await mcp.call_tool("delete_recipe", {"uuid": uid})


async def test_list_recipes(mcp, recipe_mcp):
    await mcp.call_tool("create_recipe", {"name": "Pizza"})
    await mcp.call_tool("create_recipe", {"name": "Tarte Tatin"})
    result = await mcp.call_tool("list_recipes", {})
    items = result.structured_content.get("result", result.structured_content)
    assert len(items) == 2


async def test_list_recipes_with_filter(mcp, recipe_mcp):
    await mcp.call_tool("create_recipe", {"name": "Pizza Margherita"})
    await mcp.call_tool("create_recipe", {"name": "Tarte Tatin"})
    result = await mcp.call_tool("list_recipes", {"name": "pizza"})
    items = result.structured_content.get("result", result.structured_content)
    assert len(items) == 1
