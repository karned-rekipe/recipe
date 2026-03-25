from uuid6 import uuid7


async def test_link_ustensil(mcp, recipe_mcp, ustensil_mcp, recipe_ustensil_mcp):
    recipe = await mcp.call_tool("create_recipe", {"name": "Pizza"})
    rid = recipe.structured_content["uuid"]
    ustensil = await mcp.call_tool("create_ustensil", {"name": "Fouet"})
    uid = ustensil.structured_content["uuid"]
    result = await mcp.call_tool("link_ustensil_to_recipe", {"recipe_uuid": rid, "ustensil_uuid": uid})
    assert result is not None


async def test_link_ustensil_recipe_not_found(mcp, recipe_mcp, ustensil_mcp, recipe_ustensil_mcp):
    ustensil = await mcp.call_tool("create_ustensil", {"name": "Fouet"})
    uid = ustensil.structured_content["uuid"]
    result = await mcp.call_tool("link_ustensil_to_recipe", {
        "recipe_uuid": str(uuid7()), "ustensil_uuid": uid
    })
    assert result is not None


async def test_unlink_ustensil(mcp, recipe_mcp, ustensil_mcp, recipe_ustensil_mcp):
    recipe = await mcp.call_tool("create_recipe", {"name": "Pizza"})
    rid = recipe.structured_content["uuid"]
    ustensil = await mcp.call_tool("create_ustensil", {"name": "Fouet"})
    uid = ustensil.structured_content["uuid"]
    await mcp.call_tool("link_ustensil_to_recipe", {"recipe_uuid": rid, "ustensil_uuid": uid})
    result = await mcp.call_tool("unlink_ustensil_from_recipe", {"recipe_uuid": rid, "ustensil_uuid": uid})
    assert result is not None


async def test_list_recipe_ustensils(mcp, recipe_mcp, ustensil_mcp, recipe_ustensil_mcp):
    recipe = await mcp.call_tool("create_recipe", {"name": "Pizza"})
    rid = recipe.structured_content["uuid"]
    ustensil = await mcp.call_tool("create_ustensil", {"name": "Fouet"})
    uid = ustensil.structured_content["uuid"]
    await mcp.call_tool("link_ustensil_to_recipe", {"recipe_uuid": rid, "ustensil_uuid": uid})
    result = await mcp.call_tool("list_recipe_ustensils", {"recipe_uuid": rid})
    items = result.structured_content.get("result", result.structured_content)
    assert len(items) >= 1
