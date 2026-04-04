"""FastAPI routers."""

from adapters.input.fastapi.routers.admin_router import AdminRouter
from adapters.input.fastapi.routers.recipe_router import RecipeRouter

__all__ = ["AdminRouter", "RecipeRouter"]

