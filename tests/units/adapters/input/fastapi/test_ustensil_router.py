import pytest
from fastapi.testclient import TestClient

from adapters.input.fastapi.ustensil_router import UstensilRouter
from tests.units.adapters.input.fastapi.helpers import make_test_app


@pytest.fixture
def client(ustensil_service, logger):
    app = make_test_app(UstensilRouter(ustensil_service, logger).router)
    return TestClient(app)


def test_create_ustensil(client):
    r = client.post("/v1/ustensils/", json = {"name": "Fouet"})
    assert r.status_code == 201
    assert "uuid" in r.json()


def test_list_ustensils_empty(client):
    r = client.get("/v1/ustensils/")
    assert r.status_code == 200
    assert r.json() == []


def test_list_ustensils(client):
    client.post("/v1/ustensils/", json = {"name": "Fouet"})
    client.post("/v1/ustensils/", json = {"name": "Spatule"})
    r = client.get("/v1/ustensils/")
    assert len(r.json()) == 2


def test_list_ustensils_filter(client):
    client.post("/v1/ustensils/", json = {"name": "Grand fouet"})
    client.post("/v1/ustensils/", json = {"name": "Spatule"})
    r = client.get("/v1/ustensils/?name=fouet")
    assert len(r.json()) == 1


def test_get_ustensil(client):
    created = client.post("/v1/ustensils/", json = {"name": "Fouet"}).json()
    r = client.get(f"/v1/ustensils/{created['uuid']}")
    assert r.status_code == 200
    assert r.json()["name"] == "Fouet"


def test_get_ustensil_not_found(client):
    from uuid6 import uuid7
    r = client.get(f"/v1/ustensils/{uuid7()}")
    assert r.status_code == 404


def test_update_ustensil(client):
    created = client.post("/v1/ustensils/", json = {"name": "Fouet"}).json()
    r = client.put(f"/v1/ustensils/{created['uuid']}", json = {"name": "Grand fouet"})
    assert r.status_code == 204


def test_update_ustensil_unknown_uuid(client):
    from uuid6 import uuid7
    r = client.put(f"/v1/ustensils/{uuid7()}", json = {"name": "Fouet"})
    assert r.status_code == 204


def test_patch_ustensil(client):
    created = client.post("/v1/ustensils/", json = {"name": "Fouet"}).json()
    r = client.patch(f"/v1/ustensils/{created['uuid']}", json = {"name": "Petit fouet"})
    assert r.status_code == 204


def test_patch_ustensil_not_found(client):
    from uuid6 import uuid7
    r = client.patch(f"/v1/ustensils/{uuid7()}", json = {"name": "Fouet"})
    assert r.status_code == 404


def test_delete_ustensil(client):
    created = client.post("/v1/ustensils/", json = {"name": "Fouet"}).json()
    r = client.delete(f"/v1/ustensils/{created['uuid']}")
    assert r.status_code == 204


def test_duplicate_ustensil(client):
    created = client.post("/v1/ustensils/", json = {"name": "Fouet"}).json()
    r = client.post(f"/v1/ustensils/{created['uuid']}/duplicate")
    assert r.status_code == 201
    assert r.json()["uuid"] != created["uuid"]


def test_purge_ustensils(client):
    r = client.delete("/v1/ustensils/purge")
    assert r.status_code == 200
