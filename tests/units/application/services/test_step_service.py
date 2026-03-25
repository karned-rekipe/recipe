import pytest
from uuid6 import uuid7

from adapters.output.memory.step_repository import InMemoryStepRepository
from application.services.step_service import StepService
from domain.models.step import Step
from tests.units.conftest import NullLogger


@pytest.fixture
def step_repo():
    return InMemoryStepRepository()


@pytest.fixture
def logger():
    return NullLogger()


@pytest.fixture
def service(step_repo, logger):
    return StepService(step_repo, logger)


async def test_create_and_read(service):
    step = await service.create(Step(name = "Pétrir"))
    found = await service.read(step.uuid)
    assert found.name == "Pétrir"


async def test_find_by_name(service):
    await service.create(Step(name = "Pétrir la pâte"))
    await service.create(Step(name = "Cuire"))
    result = await service.find_by_name("pétrir")
    assert len(result) == 1


async def test_find_by_name_no_result(service):
    await service.create(Step(name = "Pétrir"))
    assert await service.find_by_name("cuire") == []


async def test_find_by_recipe(service):
    rid = uuid7()
    await service.create(Step(name = "Pétrir", recipe_uuid = rid))
    await service.create(Step(name = "Cuire", recipe_uuid = rid))
    await service.create(Step(name = "Autre", recipe_uuid = uuid7()))
    result = await service.find_by_recipe(rid)
    assert len(result) == 2


async def test_find_by_recipe_empty(service):
    result = await service.find_by_recipe(uuid7())
    assert result == []


async def test_read_unknown_returns_none(service):
    assert await service.read(uuid7()) is None
