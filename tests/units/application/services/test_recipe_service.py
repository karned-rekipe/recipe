import pytest
from uuid6 import uuid7

from adapters.output.memory.repositories.ingredient_repository import InMemoryIngredientRepository
from adapters.output.memory.repositories.recipe_repository import InMemoryRecipeRepository
from adapters.output.memory.repositories.ustensil_repository import InMemoryUstensilRepository
from application.services.recipe_service import RecipeService
from domain.models.ingredient import Ingredient
from domain.models.recipe import Recipe
from domain.models.ustensil import Ustensil
from tests.units.conftest import NullLogger


@pytest.fixture
def recipe_repo():
    return InMemoryRecipeRepository()


@pytest.fixture
def ingredient_repo():
    return InMemoryIngredientRepository()


@pytest.fixture
def ustensil_repo():
    return InMemoryUstensilRepository()


@pytest.fixture
def logger():
    return NullLogger()


@pytest.fixture
def service(recipe_repo, ingredient_repo, ustensil_repo, logger):
    return RecipeService(recipe_repo, ingredient_repo, ustensil_repo, logger)


async def test_create_and_read(service):
    recipe = await service.create(Recipe(name = "Pizza"))
    found = await service.read(recipe.uuid)
    assert found.name == "Pizza"


async def test_find_by_name(service):
    await service.create(Recipe(name = "Pizza Margherita"))
    await service.create(Recipe(name = "Tarte Tatin"))
    result = await service.find_by_name("pizza")
    assert len(result) == 1
    assert result[0].name == "Pizza Margherita"


async def test_find_by_name_no_result(service):
    await service.create(Recipe(name = "Pizza"))
    assert await service.find_by_name("sushi") == []


async def test_add_ingredient(service, ingredient_repo):
    recipe = await service.create(Recipe(name = "Pizza"))
    ingredient = await ingredient_repo.create(Ingredient(name = "Farine"))
    result = await service.add_ingredient(recipe.uuid, ingredient.uuid)
    assert len(result.ingredients) == 1


async def test_remove_ingredient(service, ingredient_repo):
    ingredient = await ingredient_repo.create(Ingredient(name = "Farine"))
    recipe = await service.create(Recipe(name = "Pizza", ingredients = [ingredient]))
    await service.remove_ingredient(recipe.uuid, ingredient.uuid)
    updated = await service.read(recipe.uuid)
    assert not updated.ingredients


async def test_add_ustensil(service, ustensil_repo):
    recipe = await service.create(Recipe(name = "Pizza"))
    ustensil = await ustensil_repo.create(Ustensil(name = "Fouet"))
    result = await service.add_ustensil(recipe.uuid, ustensil.uuid)
    assert len(result.ustensils) == 1


async def test_remove_ustensil(service, ustensil_repo):
    ustensil = await ustensil_repo.create(Ustensil(name = "Fouet"))
    recipe = await service.create(Recipe(name = "Pizza", ustensils = [ustensil]))
    await service.remove_ustensil(recipe.uuid, ustensil.uuid)
    updated = await service.read(recipe.uuid)
    assert not updated.ustensils


async def test_read_unknown_returns_none(service):
    assert await service.read(uuid7()) is None
