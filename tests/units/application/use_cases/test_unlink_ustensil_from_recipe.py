import pytest
from uuid6 import uuid7

from adapters.output.memory.repositories.recipe_repository import InMemoryRecipeRepository
from adapters.output.memory.repositories.ustensil_repository import InMemoryUstensilRepository
from application.use_cases.unlink_ustensil_from_recipe import UnlinkUstensilFromRecipeUseCase
from domain.models.recipe import Recipe
from domain.models.ustensil import Ustensil
from tests.units.conftest import NullLogger


@pytest.fixture
def recipe_repo():
    return InMemoryRecipeRepository()


@pytest.fixture
def ustensil_repo():
    return InMemoryUstensilRepository()


@pytest.fixture
def logger():
    return NullLogger()


@pytest.fixture
def use_case(recipe_repo, logger):
    return UnlinkUstensilFromRecipeUseCase(recipe_repo, logger)


async def test_unlink_ustensil(use_case, recipe_repo, ustensil_repo):
    ustensil = await ustensil_repo.create(Ustensil(name = "Fouet"))
    recipe = await recipe_repo.create(Recipe(name = "Pizza", ustensils = [ustensil]))
    await use_case.execute(recipe.uuid, ustensil.uuid)
    updated = await recipe_repo.read(recipe.uuid)
    assert updated.ustensils is None or len(updated.ustensils) == 0


async def test_unlink_recipe_not_found(use_case):
    with pytest.raises(ValueError, match = "not found"):
        await use_case.execute(uuid7(), uuid7())


async def test_unlink_ustensil_not_in_recipe(use_case, recipe_repo):
    recipe = await recipe_repo.create(Recipe(name = "Pizza"))
    await use_case.execute(recipe.uuid, uuid7())


async def test_unlink_one_of_two_ustensils(use_case, recipe_repo, ustensil_repo):
    u1 = await ustensil_repo.create(Ustensil(name = "Fouet"))
    u2 = await ustensil_repo.create(Ustensil(name = "Spatule"))
    recipe = await recipe_repo.create(Recipe(name = "Pizza", ustensils = [u1, u2]))
    await use_case.execute(recipe.uuid, u1.uuid)
    updated = await recipe_repo.read(recipe.uuid)
    assert len(updated.ustensils) == 1
    assert updated.ustensils[0].uuid == u2.uuid
