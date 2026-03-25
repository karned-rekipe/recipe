import asyncio
import pytest
from fastapi.testclient import TestClient

from adapters.input.fastapi.routers.step_router import StepRouter
from domain.models.recipe import Recipe
from tests.units.adapters.input.fastapi.helpers import make_test_app


@pytest.fixture
def client(step_service, recipe_service, logger):
    app = make_test_app(StepRouter(step_service, recipe_service, logger).router)
    return TestClient(app)


@pytest.fixture
def recipe_uuid(recipe_service):
    recipe = asyncio.run(recipe_service.create(Recipe(name = "Pizza")))
    return str(recipe.uuid)


def test_create_step(client, recipe_uuid):
    r = client.post(f"/v1/recipes/{recipe_uuid}/steps/", json = {"name": "Pétrir"})
    assert r.status_code == 201
    assert "uuid" in r.json()


def test_create_step_with_description(client, recipe_uuid):
    r = client.post(f"/v1/recipes/{recipe_uuid}/steps/", json = {"name": "Cuire", "description": "20 min"})
    assert r.status_code == 201


def test_create_step_recipe_not_found(client):
    from uuid6 import uuid7
    r = client.post(f"/v1/recipes/{uuid7()}/steps/", json = {"name": "Pétrir"})
    assert r.status_code == 404


def test_list_steps(client, recipe_uuid):
    client.post(f"/v1/recipes/{recipe_uuid}/steps/", json = {"name": "Pétrir"})
    client.post(f"/v1/recipes/{recipe_uuid}/steps/", json = {"name": "Cuire"})
    r = client.get(f"/v1/recipes/{recipe_uuid}/steps/")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_list_steps_filter_by_name(client, recipe_uuid):
    client.post(f"/v1/recipes/{recipe_uuid}/steps/", json = {"name": "Pétrir la pâte"})
    client.post(f"/v1/recipes/{recipe_uuid}/steps/", json = {"name": "Cuire"})
    r = client.get(f"/v1/recipes/{recipe_uuid}/steps/?name=pétrir")
    assert len(r.json()) == 1


def test_list_steps_recipe_not_found(client):
    from uuid6 import uuid7
    r = client.get(f"/v1/recipes/{uuid7()}/steps/")
    assert r.status_code == 404


def test_get_step(client, recipe_uuid):
    created = client.post(f"/v1/recipes/{recipe_uuid}/steps/", json = {"name": "Pétrir"}).json()
    r = client.get(f"/v1/recipes/{recipe_uuid}/steps/{created['uuid']}")
    assert r.status_code == 200
    assert r.json()["name"] == "Pétrir"


def test_get_step_not_found(client, recipe_uuid):
    from uuid6 import uuid7
    r = client.get(f"/v1/recipes/{recipe_uuid}/steps/{uuid7()}")
    assert r.status_code == 404


def test_update_step(client, recipe_uuid):
    created = client.post(f"/v1/recipes/{recipe_uuid}/steps/", json = {"name": "Pétrir"}).json()
    r = client.put(f"/v1/recipes/{recipe_uuid}/steps/{created['uuid']}", json = {"name": "Pétrir 10 min"})
    assert r.status_code == 204


def test_update_step_not_found(client, recipe_uuid):
    from uuid6 import uuid7
    r = client.put(f"/v1/recipes/{recipe_uuid}/steps/{uuid7()}", json = {"name": "Pétrir"})
    assert r.status_code == 404


def test_patch_step(client, recipe_uuid):
    created = client.post(f"/v1/recipes/{recipe_uuid}/steps/", json = {"name": "Pétrir"}).json()
    r = client.patch(f"/v1/recipes/{recipe_uuid}/steps/{created['uuid']}", json = {"description": "Bien mélanger"})
    assert r.status_code == 204


def test_patch_step_not_found(client, recipe_uuid):
    from uuid6 import uuid7
    r = client.patch(f"/v1/recipes/{recipe_uuid}/steps/{uuid7()}", json = {})
    assert r.status_code == 404


def test_delete_step(client, recipe_uuid):
    created = client.post(f"/v1/recipes/{recipe_uuid}/steps/", json = {"name": "Pétrir"}).json()
    r = client.delete(f"/v1/recipes/{recipe_uuid}/steps/{created['uuid']}")
    assert r.status_code == 204


def test_delete_step_not_found(client, recipe_uuid):
    from uuid6 import uuid7
    r = client.delete(f"/v1/recipes/{recipe_uuid}/steps/{uuid7()}")
    assert r.status_code == 404


def test_duplicate_step(client, recipe_uuid):
    created = client.post(f"/v1/recipes/{recipe_uuid}/steps/", json = {"name": "Pétrir"}).json()
    r = client.post(f"/v1/recipes/{recipe_uuid}/steps/{created['uuid']}/duplicate")
    assert r.status_code == 201
    assert r.json()["uuid"] != created["uuid"]


def test_duplicate_step_not_found(client, recipe_uuid):
    from uuid6 import uuid7
    r = client.post(f"/v1/recipes/{recipe_uuid}/steps/{uuid7()}/duplicate")
    assert r.status_code == 404


def test_purge_steps(client, recipe_uuid):
    r = client.delete(f"/v1/recipes/{recipe_uuid}/steps/purge")
    assert r.status_code == 200
