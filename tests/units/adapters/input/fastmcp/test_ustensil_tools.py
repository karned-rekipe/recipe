from uuid6 import uuid7


async def test_create_ustensil(mcp, ustensil_mcp):
    result = await mcp.call_tool("create_ustensil", {"name": "Fouet"})
    assert result.structured_content["name"] == "Fouet"


async def test_get_ustensil(mcp, ustensil_mcp):
    created = await mcp.call_tool("create_ustensil", {"name": "Spatule"})
    uid = created.structured_content["uuid"]
    result = await mcp.call_tool("get_ustensil", {"uuid": uid})
    data = result.structured_content.get("result", result.structured_content)
    assert data["name"] == "Spatule"


async def test_get_ustensil_not_found(mcp, ustensil_mcp):
    result = await mcp.call_tool("get_ustensil", {"uuid": str(uuid7())})
    assert result.structured_content is None or result.structured_content.get("result") is None


async def test_update_ustensil(mcp, ustensil_mcp):
    created = await mcp.call_tool("create_ustensil", {"name": "Fouet"})
    uid = created.structured_content["uuid"]
    result = await mcp.call_tool("update_ustensil", {"uuid": uid, "name": "Grand fouet"})
    assert result is not None


async def test_delete_ustensil(mcp, ustensil_mcp):
    created = await mcp.call_tool("create_ustensil", {"name": "Spatule"})
    uid = created.structured_content["uuid"]
    await mcp.call_tool("delete_ustensil", {"uuid": uid})


async def test_list_ustensils(mcp, ustensil_mcp):
    await mcp.call_tool("create_ustensil", {"name": "Fouet"})
    await mcp.call_tool("create_ustensil", {"name": "Spatule"})
    result = await mcp.call_tool("list_ustensils", {})
    items = result.structured_content.get("result", result.structured_content)
    assert len(items) == 2


async def test_list_ustensils_with_filter(mcp, ustensil_mcp):
    await mcp.call_tool("create_ustensil", {"name": "Grand fouet"})
    await mcp.call_tool("create_ustensil", {"name": "Spatule"})
    result = await mcp.call_tool("list_ustensils", {"name": "fouet"})
    items = result.structured_content.get("result", result.structured_content)
    assert len(items) == 1


async def test_duplicate_ustensil(mcp, ustensil_mcp):
    created = await mcp.call_tool("create_ustensil", {"name": "Fouet"})
    uid = created.structured_content["uuid"]
    result = await mcp.call_tool("duplicate_ustensil", {"uuid": uid})
    assert result.structured_content["uuid"] != uid
