import pytest

from adapters.output.memory.recipe_repository import InMemoryRecipeRepository
from domain.models.recipe import Recipe


@pytest.fixture
def repo():
    return InMemoryRecipeRepository()


async def test_create_and_read(repo):
    r = await repo.create(Recipe(name = "Pizza"))
    found = await repo.read(r.uuid)
    assert found.name == "Pizza"


async def test_find_by_name(repo):
    await repo.create(Recipe(name = "Pizza Margherita"))
    await repo.create(Recipe(name = "Tarte Tatin"))
    result = await repo.find_by_name("pizza")
    assert len(result) == 1


async def test_find_by_name_case_insensitive(repo):
    await repo.create(Recipe(name = "Pizza"))
    assert len(await repo.find_by_name("PIZZA")) == 1


async def test_find_by_name_empty(repo):
    assert await repo.find_by_name("sushi") == []
