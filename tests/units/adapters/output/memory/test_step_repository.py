import pytest
from datetime import datetime, timezone
from uuid6 import uuid7

from adapters.output.memory.step_repository import InMemoryStepRepository
from domain.models.step import Step


@pytest.fixture
def repo():
    return InMemoryStepRepository()


async def test_create_and_read(repo):
    s = await repo.create(Step(name = "Pétrir"))
    found = await repo.read(s.uuid)
    assert found.name == "Pétrir"


async def test_find_by_name(repo):
    await repo.create(Step(name = "Pétrir la pâte"))
    await repo.create(Step(name = "Cuire"))
    result = await repo.find_by_name("pétrir")
    assert len(result) == 1


async def test_find_by_recipe(repo):
    rid = uuid7()
    await repo.create(Step(name = "Pétrir", recipe_uuid = rid))
    await repo.create(Step(name = "Cuire", recipe_uuid = rid))
    await repo.create(Step(name = "Autre", recipe_uuid = uuid7()))
    result = await repo.find_by_recipe(rid)
    assert len(result) == 2


async def test_find_by_recipe_excludes_deleted(repo):
    rid = uuid7()
    await repo.create(Step(name = "Pétrir", recipe_uuid = rid))
    deleted = Step(name = "Cuire", recipe_uuid = rid, deleted_at = datetime.now(timezone.utc))
    await repo.create(deleted)
    result = await repo.find_by_recipe(rid)
    assert len(result) == 1


async def test_find_by_name_empty(repo):
    assert await repo.find_by_name("inconnu") == []
