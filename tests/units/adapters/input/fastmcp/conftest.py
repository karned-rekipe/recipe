import fastmcp
import pytest
from arclith.domain.ports.logger import Logger, LogLevel
from typing import Any

from adapters.input.fastmcp.tools.ingredient_tools import IngredientMCP
from adapters.input.fastmcp.tools.recipe_ingredient_tools import RecipeIngredientMCP
from adapters.input.fastmcp.tools.recipe_tools import RecipeMCP
from adapters.input.fastmcp.tools.recipe_ustensil_tools import RecipeUstensilMCP
from adapters.input.fastmcp.tools.step_tools import StepMCP
from adapters.input.fastmcp.tools.ustensil_tools import UstensilMCP
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


@pytest.fixture
def mcp():
    return fastmcp.FastMCP("test")


@pytest.fixture
def ingredient_mcp(ingredient_service, logger, mcp):
    return IngredientMCP(ingredient_service, logger, mcp)


@pytest.fixture
def ustensil_mcp(ustensil_service, logger, mcp):
    return UstensilMCP(ustensil_service, logger, mcp)


@pytest.fixture
def recipe_mcp(recipe_service, step_service, logger, mcp):
    return RecipeMCP(recipe_service, step_service, logger, mcp)


@pytest.fixture
def step_mcp(step_service, logger, mcp):
    return StepMCP(step_service, logger, mcp)


@pytest.fixture
def recipe_ingredient_mcp(recipe_service, logger, mcp):
    return RecipeIngredientMCP(recipe_service, logger, mcp)


@pytest.fixture
def recipe_ustensil_mcp(recipe_service, logger, mcp):
    return RecipeUstensilMCP(recipe_service, logger, mcp)
