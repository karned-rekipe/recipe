from uuid import UUID as StdUUID

from arclith.domain.ports.logger import Logger
from fastapi import APIRouter, Depends, HTTPException
from uuid6 import UUID

from adapters.input.fastapi.dependencies import inject_tenant_uri
from adapters.input.schemas.ingredient_schema import IngredientCreatedSchema
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
        self.router.add_api_route("/{ingredient_uuid}", self.add_ingredient, methods = ["POST"],
                                  response_model = IngredientCreatedSchema, status_code = 201)
        self.router.add_api_route("/{ingredient_uuid}", self.remove_ingredient, methods = ["DELETE"],
                                  response_model = None, status_code = 204)

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    async def add_ingredient(self, uuid: StdUUID, ingredient_uuid: StdUUID) -> IngredientCreatedSchema:
        """Link an existing ingredient to a recipe."""
        recipe = await self._service.read(self._to_uuid6(uuid))
        if recipe is None:
            raise HTTPException(status_code = 404, detail = "Recipe not found")
        try:
            await self._service.add_ingredient(self._to_uuid6(uuid), self._to_uuid6(ingredient_uuid))
        except ValueError as e:
            raise HTTPException(status_code = 404, detail = str(e))
        return IngredientCreatedSchema(uuid = ingredient_uuid)

    async def remove_ingredient(self, uuid: StdUUID, ingredient_uuid: StdUUID) -> None:
        """Unlink an ingredient from a recipe."""
        recipe = await self._service.read(self._to_uuid6(uuid))
        if recipe is None:
            raise HTTPException(status_code = 404, detail = "Recipe not found")
        await self._service.remove_ingredient(self._to_uuid6(uuid), self._to_uuid6(ingredient_uuid))
