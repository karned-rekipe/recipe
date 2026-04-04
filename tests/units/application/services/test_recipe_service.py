import pytest
from uuid6 import uuid7

from application.services.recipe_service import RecipeService
from domain.models.recipe import Recipe


@pytest.fixture
def service(repo, logger):
    return RecipeService(repo, logger)


async def test_create_and_read(service):
    recipe = await service.create(Recipe(name="Farine"))
    found = await service.read(recipe.uuid)
    assert found is not None
    assert found.name == "Farine"


async def test_update(service):
    recipe = await service.create(Recipe(name="Farine"))
    updated = await service.update(recipe.model_copy(update={"name": "Farine complète"}))
    assert updated.name == "Farine complète"
    assert updated.version == 2


async def test_delete_hides_from_read(service):
    recipe = await service.create(Recipe(name="Sel"))
    await service.delete(recipe.uuid)
    assert await service.read(recipe.uuid) is None


async def test_find_all(service):
    await service.create(Recipe(name="Farine"))
    await service.create(Recipe(name="Sel"))
    result = await service.find_all()
    assert len(result) == 2


async def test_find_by_name(service):
    await service.create(Recipe(name="Farine de blé"))
    await service.create(Recipe(name="Sel fin"))
    result = await service.find_by_name("farine")
    assert len(result) == 1
    assert result[0].name == "Farine de blé"


async def test_duplicate(service):
    recipe = await service.create(Recipe(name="Farine"))
    clone = await service.duplicate(recipe.uuid)
    assert clone.uuid != recipe.uuid
    assert clone.name == "Farine"


async def test_read_unknown_returns_none(service):
    assert await service.read(uuid7()) is None


async def test_find_by_name_no_results(service):
    await service.create(Recipe(name="Sel"))
    result = await service.find_by_name("farine")
    assert result == []

