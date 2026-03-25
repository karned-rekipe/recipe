from uuid6 import uuid7


async def test_create_step(mcp, step_mcp, recipe_mcp):
    recipe = await mcp.call_tool("create_recipe", {"name": "Pizza"})
    rid = recipe.structured_content["uuid"]
    result = await mcp.call_tool("create_step", {"recipe_uuid": rid, "name": "Pétrir"})
    assert result.structured_content["name"] == "Pétrir"


async def test_create_step_with_description(mcp, step_mcp, recipe_mcp):
    recipe = await mcp.call_tool("create_recipe", {"name": "Pizza"})
    rid = recipe.structured_content["uuid"]
    result = await mcp.call_tool("create_step", {"recipe_uuid": rid, "name": "Cuire", "description": "20 min"})
    assert result.structured_content["description"] == "20 min"


async def test_get_step(mcp, step_mcp, recipe_mcp):
    recipe = await mcp.call_tool("create_recipe", {"name": "Pizza"})
    rid = recipe.structured_content["uuid"]
    created = await mcp.call_tool("create_step", {"recipe_uuid": rid, "name": "Pétrir"})
    sid = created.structured_content["uuid"]
    result = await mcp.call_tool("get_step", {"uuid": sid})
    data = result.structured_content.get("result", result.structured_content)
    assert data["name"] == "Pétrir"


async def test_get_step_not_found(mcp, step_mcp):
    result = await mcp.call_tool("get_step", {"uuid": str(uuid7())})
    assert result.structured_content is None or result.structured_content.get("result") is None


async def test_update_step(mcp, step_mcp, recipe_mcp):
    recipe = await mcp.call_tool("create_recipe", {"name": "Pizza"})
    rid = recipe.structured_content["uuid"]
    created = await mcp.call_tool("create_step", {"recipe_uuid": rid, "name": "Pétrir"})
    sid = created.structured_content["uuid"]
    result = await mcp.call_tool("update_step", {"uuid": sid, "name": "Pétrir 10 min"})
    assert result is not None


async def test_delete_step(mcp, step_mcp, recipe_mcp):
    recipe = await mcp.call_tool("create_recipe", {"name": "Pizza"})
    rid = recipe.structured_content["uuid"]
    created = await mcp.call_tool("create_step", {"recipe_uuid": rid, "name": "Pétrir"})
    sid = created.structured_content["uuid"]
    await mcp.call_tool("delete_step", {"uuid": sid})


async def test_list_steps(mcp, step_mcp, recipe_mcp):
    recipe = await mcp.call_tool("create_recipe", {"name": "Pizza"})
    rid = recipe.structured_content["uuid"]
    await mcp.call_tool("create_step", {"recipe_uuid": rid, "name": "Pétrir"})
    await mcp.call_tool("create_step", {"recipe_uuid": rid, "name": "Cuire"})
    result = await mcp.call_tool("list_steps_for_recipe", {"recipe_uuid": rid})
    items = result.structured_content.get("result", result.structured_content)
    assert len(items) == 2
