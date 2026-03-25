import pytest
from arclith.domain.ports.logger import Logger, LogLevel
from fastapi import FastAPI
from typing import Any

from adapters.input.fastapi.dependencies import inject_tenant_uri
from adapters.output.memory.repositories.ingredient_repository import InMemoryIngredientRepository
from adapters.output.memory.repositories.recipe_repository import InMemoryRecipeRepository
from adapters.output.memory.repositories.step_repository import InMemoryStepRepository
from adapters.output.memory.repositories.ustensil_repository import InMemoryUstensilRepository
from application.services.ingredient_service import IngredientService
from application.services.recipe_service import RecipeService
from application.services.step_service import StepService
from application.services.ustensil_service import UstensilService


class NullLogger(Logger):
    def log(self, level: LogLevel, message: str, **metadata: Any) -> None:
        pass


@pytest.fixture
def logger():
    return NullLogger()


@pytest.fixture
def ingredient_repo():
    return InMemoryIngredientRepository()


@pytest.fixture
def recipe_repo():
    return InMemoryRecipeRepository()


@pytest.fixture
def ustensil_repo():
    return InMemoryUstensilRepository()


@pytest.fixture
def step_repo():
    return InMemoryStepRepository()


@pytest.fixture
def ingredient_service(ingredient_repo, logger):
    return IngredientService(ingredient_repo, logger)


@pytest.fixture
def ustensil_service(ustensil_repo, logger):
    return UstensilService(ustensil_repo, logger)


@pytest.fixture
def recipe_service(recipe_repo, ingredient_repo, ustensil_repo, logger):
    return RecipeService(recipe_repo, ingredient_repo, ustensil_repo, logger)


@pytest.fixture
def step_service(step_repo, logger):
    return StepService(step_repo, logger)


def make_app(*routers) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[inject_tenant_uri] = lambda: None
    for router in routers:
        app.include_router(router)
    return app
