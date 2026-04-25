"""MCP tools registration."""

import fastmcp
from adapters.input.fastmcp.tools import AdminMCP, EquipmentMCP, IngredientGroupMCP, IngredientMCP, IngredientRayonMCP, RecipeMCP, TagMCP
from arclith import Arclith
from infrastructure.containers.equipment_container import build_equipment_service
from infrastructure.containers.ingredient_group_container import build_ingredient_group_service
from infrastructure.containers.ingredient_container import build_ingredient_service
from infrastructure.containers.ingredient_rayon_container import build_ingredient_rayon_service
from infrastructure.containers.recipe_container import build_recipe_service
from infrastructure.containers.tag_container import build_tag_service
from infrastructure.purge_registry import purge_registry


def register_tools(mcp: fastmcp.FastMCP, arclith: Arclith) -> None:
    """Register all MCP tools."""
    group_service, group_logger = build_ingredient_group_service(arclith)
    rayon_service, rayon_logger = build_ingredient_rayon_service(arclith)
    ingredient_service, ingredient_logger = build_ingredient_service(
        arclith,
        group_repository=group_service.repository,
        rayon_repository=rayon_service.repository,
    )
    equipment_service, equipment_logger = build_equipment_service(arclith)
    tag_service, tag_logger = build_tag_service(arclith)
    recipe_service, logger = build_recipe_service(
        arclith,
        ingredient_repository=ingredient_service.repository,
        equipment_repository=equipment_service.repository,
        tag_repository=tag_service.repository,
        group_repository=group_service.repository,
        rayon_repository=rayon_service.repository,
    )

    purge_registry.register("recipes", recipe_service.purge)
    RecipeMCP(recipe_service, logger, mcp)

    purge_registry.register("ingredients", ingredient_service.purge)
    IngredientMCP(ingredient_service, ingredient_logger, mcp, recipe_service)

    purge_registry.register("equipment", equipment_service.purge)
    EquipmentMCP(equipment_service, equipment_logger, mcp, recipe_service)

    purge_registry.register("tags", tag_service.purge)
    TagMCP(tag_service, tag_logger, mcp, recipe_service)

    purge_registry.register("ingredient_groups", group_service.purge)
    IngredientGroupMCP(group_service, group_logger, mcp, ingredient_service)

    purge_registry.register("ingredient_rayons", rayon_service.purge)
    IngredientRayonMCP(rayon_service, rayon_logger, mcp, ingredient_service)

    AdminMCP(purge_registry, logger, mcp)
