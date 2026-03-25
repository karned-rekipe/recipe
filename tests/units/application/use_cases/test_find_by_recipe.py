import pytest
from uuid6 import uuid7

from adapters.output.memory.repositories.step_repository import InMemoryStepRepository
from application.use_cases.find_by_recipe import FindByRecipeUseCase
from domain.models.step import Step
from tests.units.conftest import NullLogger


@pytest.fixture
def step_repo():
    return InMemoryStepRepository()


@pytest.fixture
def logger():
    return NullLogger()


@pytest.fixture
def use_case(step_repo, logger):
    return FindByRecipeUseCase(step_repo, logger)


async def test_find_by_recipe_returns_steps(use_case, step_repo):
    rid = uuid7()
    await step_repo.create(Step(name = "Pétrir", recipe_uuid = rid))
    await step_repo.create(Step(name = "Cuire", recipe_uuid = rid))
    result = await use_case.execute(rid)
    assert len(result) == 2


async def test_find_by_recipe_excludes_other_recipes(use_case, step_repo):
    rid1, rid2 = uuid7(), uuid7()
    await step_repo.create(Step(name = "Pétrir", recipe_uuid = rid1))
    await step_repo.create(Step(name = "Cuire", recipe_uuid = rid2))
    result = await use_case.execute(rid1)
    assert len(result) == 1
    assert result[0].name == "Pétrir"


async def test_find_by_recipe_empty(use_case):
    result = await use_case.execute(uuid7())
    assert result == []
