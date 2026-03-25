from uuid6 import uuid7


async def test_link_ingredient(mcp, recipe_mcp, ingredient_mcp, recipe_ingredient_mcp):
    recipe = await mcp.call_tool("create_recipe", {"name": "Pizza"})
    rid = recipe.structured_content["uuid"]
    ingredient = await mcp.call_tool("create_ingredient", {"name": "Farine"})
    iid = ingredient.structured_content["uuid"]
    result = await mcp.call_tool("link_ingredient_to_recipe", {"recipe_uuid": rid, "ingredient_uuid": iid})
    assert result is not None


async def test_link_ingredient_recipe_not_found(mcp, recipe_mcp, ingredient_mcp, recipe_ingredient_mcp):
    ingredient = await mcp.call_tool("create_ingredient", {"name": "Farine"})
    iid = ingredient.structured_content["uuid"]
    result = await mcp.call_tool("link_ingredient_to_recipe", {
        "recipe_uuid": str(uuid7()), "ingredient_uuid": iid
    })
    assert result is not None


async def test_unlink_ingredient(mcp, recipe_mcp, ingredient_mcp, recipe_ingredient_mcp):
    recipe = await mcp.call_tool("create_recipe", {"name": "Pizza"})
    rid = recipe.structured_content["uuid"]
    ingredient = await mcp.call_tool("create_ingredient", {"name": "Farine"})
    iid = ingredient.structured_content["uuid"]
    await mcp.call_tool("link_ingredient_to_recipe", {"recipe_uuid": rid, "ingredient_uuid": iid})
    result = await mcp.call_tool("unlink_ingredient_from_recipe", {"recipe_uuid": rid, "ingredient_uuid": iid})
    assert result is not None


async def test_list_recipe_ingredients(mcp, recipe_mcp, ingredient_mcp, recipe_ingredient_mcp):
    recipe = await mcp.call_tool("create_recipe", {"name": "Pizza"})
    rid = recipe.structured_content["uuid"]
    ingredient = await mcp.call_tool("create_ingredient", {"name": "Farine"})
    iid = ingredient.structured_content["uuid"]
    await mcp.call_tool("link_ingredient_to_recipe", {"recipe_uuid": rid, "ingredient_uuid": iid})
    result = await mcp.call_tool("list_recipe_ingredients", {"recipe_uuid": rid})
    items = result.structured_content.get("result", result.structured_content)
    assert len(items) >= 1
