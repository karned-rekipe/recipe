import pytest
from uuid6 import uuid7

from adapters.output.memory.ingredient_repository import InMemoryIngredientRepository
from adapters.output.memory.recipe_repository import InMemoryRecipeRepository
from application.use_cases.unlink_ingredient_from_recipe import UnlinkIngredientFromRecipeUseCase
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
def use_case(recipe_repo, logger):
    return UnlinkIngredientFromRecipeUseCase(recipe_repo, logger)


async def test_unlink_ingredient(use_case, recipe_repo, ingredient_repo):
    ingredient = await ingredient_repo.create(Ingredient(name = "Farine"))
    recipe = await recipe_repo.create(Recipe(name = "Pizza", ingredients = [ingredient]))
    await use_case.execute(recipe.uuid, ingredient.uuid)
    updated = await recipe_repo.read(recipe.uuid)
    assert updated.ingredients is None or len(updated.ingredients) == 0


async def test_unlink_recipe_not_found(use_case):
    with pytest.raises(ValueError, match = "not found"):
        await use_case.execute(uuid7(), uuid7())


async def test_unlink_ingredient_not_in_recipe(use_case, recipe_repo):
    recipe = await recipe_repo.create(Recipe(name = "Pizza"))
    await use_case.execute(recipe.uuid, uuid7())


async def test_unlink_one_of_two_ingredients(use_case, recipe_repo, ingredient_repo):
    i1 = await ingredient_repo.create(Ingredient(name = "Farine"))
    i2 = await ingredient_repo.create(Ingredient(name = "Sel"))
    recipe = await recipe_repo.create(Recipe(name = "Pizza", ingredients = [i1, i2]))
    await use_case.execute(recipe.uuid, i1.uuid)
    updated = await recipe_repo.read(recipe.uuid)
    assert len(updated.ingredients) == 1
    assert updated.ingredients[0].uuid == i2.uuid
