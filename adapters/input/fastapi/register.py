from adapters.input.fastapi.routers import (
    AdminRouter,
    EquipmentRouter,
    IngredientGroupRouter,
    IngredientRayonRouter,
    IngredientRouter,
    RecipeRouter,
    TagRouter,
    UnitRouter,
)
from arclith import Arclith
from fastapi import FastAPI
from infrastructure.containers.equipment_container import build_equipment_service
from infrastructure.containers.ingredient_group_container import build_ingredient_group_service
from infrastructure.containers.ingredient_container import build_ingredient_service
from infrastructure.containers.ingredient_enrichment_suggestion_container import build_ingredient_enrichment_suggestion_service
from infrastructure.containers.ingredient_image_generation_agent_container import build_ingredient_image_generation_agent
from infrastructure.containers.ingredient_rayon_container import build_ingredient_rayon_service
from infrastructure.containers.image_generator_container import build_image_generator
from infrastructure.containers.recipe_container import build_recipe_service
from infrastructure.containers.recipe_ai_enrichment_agent_container import build_recipe_ai_enrichment_agent
from infrastructure.containers.tag_container import build_tag_service
from infrastructure.purge_registry import purge_registry


def register_routers(app: FastAPI, arclith: Arclith) -> None:
    image_generator = build_image_generator()
    group_service, group_logger = build_ingredient_group_service(arclith)
    rayon_service, rayon_logger = build_ingredient_rayon_service(arclith)
    ingredient_service, ingredient_logger = build_ingredient_service(
        arclith,
        group_repository=group_service.repository,
        rayon_repository=rayon_service.repository,
        image_generation_agent=build_ingredient_image_generation_agent(),
    )
    equipment_service, equipment_logger = build_equipment_service(arclith, image_generator=image_generator)
    tag_service, tag_logger = build_tag_service(arclith)
    recipe_service, logger = build_recipe_service(
        arclith,
        ingredient_repository=ingredient_service.repository,
        equipment_repository=equipment_service.repository,
        tag_repository=tag_service.repository,
        group_repository=group_service.repository,
        rayon_repository=rayon_service.repository,
        image_generator=image_generator,
        ai_enrichment_agent=build_recipe_ai_enrichment_agent(),
    )
    suggestion_service, _ = build_ingredient_enrichment_suggestion_service(
        arclith,
        ingredient_service.repository,
    )

    purge_registry.register("recipes", recipe_service.purge)
    app.include_router(RecipeRouter(recipe_service, logger).router)

    purge_registry.register("ingredients", ingredient_service.purge)
    app.include_router(IngredientRouter(ingredient_service, ingredient_logger, recipe_service, suggestion_service).router)
    purge_registry.register("ingredient_enrichment_suggestions", suggestion_service.purge)
    app.include_router(UnitRouter(ingredient_service).router)

    purge_registry.register("equipment", equipment_service.purge)
    app.include_router(EquipmentRouter(equipment_service, equipment_logger, recipe_service).router)

    purge_registry.register("tags", tag_service.purge)
    app.include_router(TagRouter(tag_service, tag_logger, recipe_service).router)

    purge_registry.register("ingredient_groups", group_service.purge)
    app.include_router(IngredientGroupRouter(group_service, group_logger, ingredient_service).router)

    purge_registry.register("ingredient_rayons", rayon_service.purge)
    app.include_router(IngredientRayonRouter(rayon_service, rayon_logger, ingredient_service).router)

    app.include_router(AdminRouter(purge_registry).router)
