from arclith.adapters.input.schemas import ApiResponse, success_response
from arclith.domain.ports.logger import Logger
from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID as StdUUID
from uuid6 import UUID

from adapters.input.fastapi.dependencies import inject_tenant_uri
from adapters.input.schemas.ingredient_schema import IngredientCreatedSchema, IngredientSchema
from application.services.recipe_service import RecipeService


class RecipeIngredientRouter:
    def __init__(self, service: RecipeService, logger: Logger) -> None:
        self._service = service
        self._logger = logger
        self.router = APIRouter(
            prefix = "/v1/recipes/{uuid}/ingredients",
            tags = ["recipes : ingredients"],
            dependencies = [Depends(inject_tenant_uri)],
        )
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route(
            methods = ["GET"],
            path = "/",
            endpoint = self.list_ingredients,
            summary = "List recipe ingredients",
            response_model = ApiResponse[list[IngredientSchema]],
            response_description = "Ingredients linked to the recipe",
            responses = {404: {"description": "Recipe not found"}},
        )
        self.router.add_api_route(
            methods = ["POST"],
            path = "/{ingredient_uuid}",
            endpoint = self.add_ingredient,
            summary = "Link ingredient to recipe",
            response_model = ApiResponse[IngredientCreatedSchema],
            response_description = "UUID of the linked ingredient",
            status_code = 201,
            responses = {404: {"description": "Recipe or ingredient not found"}},
        )
        self.router.add_api_route(
            methods = ["DELETE"],
            path = "/{ingredient_uuid}",
            endpoint = self.remove_ingredient,
            summary = "Unlink ingredient from recipe",
            status_code = 204,
            response_model = None,
        )

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    async def list_ingredients(self, uuid: StdUUID) -> ApiResponse[list[IngredientSchema]]:
        """List all ingredients currently linked to the recipe."""
        recipe = await self._service.read(self._to_uuid6(uuid))
        if recipe is None:
            self._logger.warning("⚠️ Recipe not found via HTTP", uuid = str(uuid))
            raise HTTPException(status_code = 404, detail = "Recipe not found")
        data = [IngredientSchema.model_validate(i, from_attributes = True) for i in (recipe.ingredients or [])]
        return success_response(
            data = data,
            links = {"self": f"/v1/recipes/{uuid}/ingredients"},
        )

    async def add_ingredient(self, uuid: StdUUID, ingredient_uuid: StdUUID) -> ApiResponse[IngredientCreatedSchema]:
        """Link an existing ingredient to a recipe."""
        recipe = await self._service.read(self._to_uuid6(uuid))
        if recipe is None:
            raise HTTPException(status_code = 404, detail = "Recipe not found")
        try:
            await self._service.add_ingredient(self._to_uuid6(uuid), self._to_uuid6(ingredient_uuid))
        except ValueError as e:
            raise HTTPException(status_code = 404, detail = str(e))
        return success_response(
            data = IngredientCreatedSchema(uuid = ingredient_uuid),
            links = {
                "self": f"/v1/recipes/{uuid}/ingredients/{ingredient_uuid}",
                "collection": f"/v1/recipes/{uuid}/ingredients",
                "ingredient": f"/v1/ingredients/{ingredient_uuid}",
            },
        )

    async def remove_ingredient(self, uuid: StdUUID, ingredient_uuid: StdUUID) -> None:
        """Unlink an ingredient from a recipe."""
        recipe = await self._service.read(self._to_uuid6(uuid))
        if recipe is None:
            raise HTTPException(status_code = 404, detail = "Recipe not found")
        await self._service.remove_ingredient(self._to_uuid6(uuid), self._to_uuid6(ingredient_uuid))
