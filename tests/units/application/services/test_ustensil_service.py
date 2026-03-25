import pytest
from uuid6 import uuid7

from adapters.output.memory.ustensil_repository import InMemoryUstensilRepository
from application.services.ustensil_service import UstensilService
from domain.models.ustensil import Ustensil
from tests.units.conftest import NullLogger


@pytest.fixture
def ustensil_repo():
    return InMemoryUstensilRepository()


@pytest.fixture
def logger():
    return NullLogger()


@pytest.fixture
def service(ustensil_repo, logger):
    return UstensilService(ustensil_repo, logger)


async def test_create_and_read(service):
    u = await service.create(Ustensil(name = "Fouet"))
    found = await service.read(u.uuid)
    assert found.name == "Fouet"


async def test_find_by_name(service):
    await service.create(Ustensil(name = "Grand fouet"))
    await service.create(Ustensil(name = "Spatule"))
    result = await service.find_by_name("fouet")
    assert len(result) == 1
    assert result[0].name == "Grand fouet"


async def test_find_by_name_no_result(service):
    await service.create(Ustensil(name = "Fouet"))
    assert await service.find_by_name("cuillère") == []


async def test_read_unknown_returns_none(service):
    assert await service.read(uuid7()) is None
