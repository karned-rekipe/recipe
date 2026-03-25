import pytest

from adapters.output.memory.repositories.ustensil_repository import InMemoryUstensilRepository
from domain.models.ustensil import Ustensil


@pytest.fixture
def repo():
    return InMemoryUstensilRepository()


async def test_create_and_read(repo):
    u = await repo.create(Ustensil(name = "Fouet"))
    found = await repo.read(u.uuid)
    assert found.name == "Fouet"


async def test_find_by_name(repo):
    await repo.create(Ustensil(name = "Grand fouet"))
    await repo.create(Ustensil(name = "Spatule"))
    result = await repo.find_by_name("fouet")
    assert len(result) == 1


async def test_find_by_name_case_insensitive(repo):
    await repo.create(Ustensil(name = "Fouet"))
    assert len(await repo.find_by_name("FOUET")) == 1


async def test_find_by_name_empty(repo):
    assert await repo.find_by_name("casserole") == []
