import pytest
from uuid6 import uuid7

from adapters.output.memory.ingredient_repository import InMemoryIngredientRepository
from adapters.output.memory.recipe_repository import InMemoryRecipeRepository
from application.use_cases.link_ingredient_to_recipe import LinkIngredientToRecipeUseCase
from domain.models.ingredient import Ingredient
from domain.models.recipe import Recipe
from tests.units.conftest import NullLogger


@pytest.fixture
def recipe_repo():
    return InMemoryRecipeRepository()


@pytest.fixture
def ingredient_repo():
    return InMemoryIngredientRepository()


@pytest.fixture
def logger():
    return NullLogger()


@pytest.fixture
def use_case(recipe_repo, ingredient_repo, logger):
    return LinkIngredientToRecipeUseCase(recipe_repo, ingredient_repo, logger)


async def test_link_ingredient(use_case, recipe_repo, ingredient_repo):
    recipe = await recipe_repo.create(Recipe(name = "Pizza"))
    ingredient = await ingredient_repo.create(Ingredient(name = "Farine"))
    result = await use_case.execute(recipe.uuid, ingredient.uuid)
    assert len(result.ingredients) == 1
    assert result.ingredients[0].uuid == ingredient.uuid


async def test_link_ingredient_recipe_not_found(use_case, ingredient_repo):
    ingredient = await ingredient_repo.create(Ingredient(name = "Farine"))
    with pytest.raises(ValueError, match = "not found"):
        await use_case.execute(uuid7(), ingredient.uuid)


async def test_link_ingredient_not_found(use_case, recipe_repo):
    recipe = await recipe_repo.create(Recipe(name = "Pizza"))
    with pytest.raises(ValueError, match = "not found"):
        await use_case.execute(recipe.uuid, uuid7())


async def test_link_ingredient_already_linked(use_case, recipe_repo, ingredient_repo):
    recipe = await recipe_repo.create(Recipe(name = "Pizza"))
    ingredient = await ingredient_repo.create(Ingredient(name = "Farine"))
    await use_case.execute(recipe.uuid, ingredient.uuid)
    result = await use_case.execute(recipe.uuid, ingredient.uuid)
    assert len(result.ingredients) == 1


async def test_link_multiple_ingredients(use_case, recipe_repo, ingredient_repo):
    recipe = await recipe_repo.create(Recipe(name = "Pizza"))
    i1 = await ingredient_repo.create(Ingredient(name = "Farine"))
    i2 = await ingredient_repo.create(Ingredient(name = "Sel"))
    await use_case.execute(recipe.uuid, i1.uuid)
    result = await use_case.execute(recipe.uuid, i2.uuid)
    assert len(result.ingredients) == 2
