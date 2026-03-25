import pytest
from uuid6 import uuid7

from adapters.output.memory.recipe_repository import InMemoryRecipeRepository
from adapters.output.memory.ustensil_repository import InMemoryUstensilRepository
from application.use_cases.link_ustensil_to_recipe import LinkUstensilToRecipeUseCase
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
def use_case(recipe_repo, ustensil_repo, logger):
    return LinkUstensilToRecipeUseCase(recipe_repo, ustensil_repo, logger)


async def test_link_ustensil(use_case, recipe_repo, ustensil_repo):
    recipe = await recipe_repo.create(Recipe(name = "Pizza"))
    ustensil = await ustensil_repo.create(Ustensil(name = "Fouet"))
    result = await use_case.execute(recipe.uuid, ustensil.uuid)
    assert len(result.ustensils) == 1
    assert result.ustensils[0].uuid == ustensil.uuid


async def test_link_ustensil_recipe_not_found(use_case, ustensil_repo):
    ustensil = await ustensil_repo.create(Ustensil(name = "Fouet"))
    with pytest.raises(ValueError, match = "not found"):
        await use_case.execute(uuid7(), ustensil.uuid)


async def test_link_ustensil_not_found(use_case, recipe_repo):
    recipe = await recipe_repo.create(Recipe(name = "Pizza"))
    with pytest.raises(ValueError, match = "not found"):
        await use_case.execute(recipe.uuid, uuid7())


async def test_link_ustensil_already_linked(use_case, recipe_repo, ustensil_repo):
    recipe = await recipe_repo.create(Recipe(name = "Pizza"))
    ustensil = await ustensil_repo.create(Ustensil(name = "Fouet"))
    await use_case.execute(recipe.uuid, ustensil.uuid)
    result = await use_case.execute(recipe.uuid, ustensil.uuid)
    assert len(result.ustensils) == 1


async def test_link_multiple_ustensils(use_case, recipe_repo, ustensil_repo):
    recipe = await recipe_repo.create(Recipe(name = "Pizza"))
    u1 = await ustensil_repo.create(Ustensil(name = "Fouet"))
    u2 = await ustensil_repo.create(Ustensil(name = "Spatule"))
    await use_case.execute(recipe.uuid, u1.uuid)
    result = await use_case.execute(recipe.uuid, u2.uuid)
    assert len(result.ustensils) == 2
