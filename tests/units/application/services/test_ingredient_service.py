import pytest

from adapters.output.memory.repositories.ingredient_repository import InMemoryIngredientRepository
from application.services.ingredient_service import IngredientService
from domain.models.ingredient import Ingredient


@pytest.fixture
def ingredient_repo():
    return InMemoryIngredientRepository()


@pytest.fixture
def service(ingredient_repo, logger):
    return IngredientService(ingredient_repo, logger)


async def test_create_and_read(service):
    ingredient = await service.create(Ingredient(name="Tomate"))
    found = await service.read(ingredient.uuid)
    assert found is not None
    assert found.name == "Tomate"


async def test_create_with_all_fields(service):
    ingredient = await service.create(Ingredient(
        name="Tomate",
        rayon="fruits et légumes",
        group="légumes",
        green_score=80,
        unit="g",
        quantity=100.0,
        season_months={7: 3, 8: 3},
    ))
    found = await service.read(ingredient.uuid)
    assert found is not None
    assert found.rayon == "fruits et légumes"
    assert found.season_months == {7: 3, 8: 3}


async def test_update(service):
    ingredient = await service.create(Ingredient(name="Tomate"))
    updated = await service.update(ingredient.model_copy(update={"name": "Tomate cerise"}))
    assert updated.name == "Tomate cerise"
    assert updated.version == 2


async def test_delete_hides_from_read(service):
    ingredient = await service.create(Ingredient(name="Sel"))
    await service.delete(ingredient.uuid)
    assert await service.read(ingredient.uuid) is None


async def test_find_all(service):
    await service.create(Ingredient(name="Tomate"))
    await service.create(Ingredient(name="Carotte"))
    result = await service.find_all()
    assert len(result) == 2


async def test_find_by_name(service):
    await service.create(Ingredient(name="Tomate cerise"))
    await service.create(Ingredient(name="Carotte"))
    result = await service.find_by_name("tomate")
    assert len(result) == 1
    assert result[0].name == "Tomate cerise"


async def test_duplicate(service):
    ingredient = await service.create(Ingredient(name="Tomate", season_months={7: 3}))
    clone = await service.duplicate(ingredient.uuid)
    assert clone.uuid != ingredient.uuid
    assert clone.name == ingredient.name
    assert clone.season_months == ingredient.season_months


async def test_find_page_filtered_no_filter(service):
    await service.create(Ingredient(name="Tomate"))
    await service.create(Ingredient(name="Carotte"))
    items, total = await service.find_page_filtered(offset=0, limit=10)
    assert total == 2
    assert len(items) == 2


async def test_find_page_filtered_with_name(service):
    await service.create(Ingredient(name="Tomate cerise"))
    await service.create(Ingredient(name="Carotte"))
    items, total = await service.find_page_filtered(name="tomate", offset=0, limit=10)
    assert total == 1
    assert items[0].name == "Tomate cerise"
