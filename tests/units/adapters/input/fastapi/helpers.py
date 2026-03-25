from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.input.fastapi.dependencies import inject_tenant_uri


def make_test_app(*routers) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[inject_tenant_uri] = lambda: None
    for router in routers:
        app.include_router(router)
    return app


def make_client(*routers) -> TestClient:
    return TestClient(make_test_app(*routers))
