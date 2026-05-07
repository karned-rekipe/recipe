"""FastAPI routers."""

from adapters.input.fastapi.routers.admin_router import AdminRouter
from adapters.input.fastapi.routers.equipment_router import EquipmentRouter
from adapters.input.fastapi.routers.ingredient_group_router import IngredientGroupRouter
from adapters.input.fastapi.routers.ingredient_router import IngredientRouter
from adapters.input.fastapi.routers.ingredient_rayon_router import IngredientRayonRouter
from adapters.input.fastapi.routers.recipe_router import RecipeRouter
from adapters.input.fastapi.routers.tag_router import TagRouter
from adapters.input.fastapi.routers.unit_router import UnitRouter

__all__ = [
    "AdminRouter",
    "EquipmentRouter",
    "IngredientGroupRouter",
    "IngredientRayonRouter",
    "IngredientRouter",
    "RecipeRouter",
    "TagRouter",
    "UnitRouter",
]
