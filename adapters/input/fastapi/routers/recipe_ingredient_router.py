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
            response_model = list[IngredientSchema],
            response_description = "Ingredients linked to the recipe",
            status_code = 200,
            responses = {404: {"description": "Recipe not found"}},
        )
        self.router.add_api_route(
            methods = ["POST"],
            path = "/{ingredient_uuid}",
            endpoint = self.add_ingredient,
            summary = "Link ingredient to recipe",
            response_model = IngredientCreatedSchema,
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
        )

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    async def list_ingredients(self, uuid: StdUUID) -> list[IngredientSchema]:
        """List all ingredients currently linked to the recipe.

        Returns the snapshot data as stored in the recipe at link time.
        Each item: uuid, name, unit, created_at, updated_at, version.
        """
        recipe = await self._service.read(self._to_uuid6(uuid))
        if recipe is None:
            self._logger.warning("⚠️ Recipe not found via HTTP", uuid = str(uuid))
            raise HTTPException(status_code = 404, detail = "Recipe not found")
        return [IngredientSchema.model_validate(i, from_attributes = True) for i in (recipe.ingredients or [])]

    async def add_ingredient(self, uuid: StdUUID, ingredient_uuid: StdUUID) -> IngredientCreatedSchema:
        """Link an existing ingredient to a recipe.

        Copies the ingredient's data (name, unit, uuid) into the recipe at the time of linking.
        The original uuid is preserved to allow future synchronisation.
        Idempotent: if the ingredient is already linked, the call is silently ignored.
        Returns the UUID of the linked ingredient.
        """
        recipe = await self._service.read(self._to_uuid6(uuid))
        if recipe is None:
            raise HTTPException(status_code = 404, detail = "Recipe not found")
        try:
            await self._service.add_ingredient(self._to_uuid6(uuid), self._to_uuid6(ingredient_uuid))
        except ValueError as e:
            raise HTTPException(status_code = 404, detail = str(e))
        return IngredientCreatedSchema(uuid = ingredient_uuid)

    async def remove_ingredient(self, uuid: StdUUID, ingredient_uuid: StdUUID) -> None:
        """Unlink an ingredient from a recipe.

        Removes the ingredient snapshot from the recipe's ingredient list.
        Silent no-op if the ingredient is not currently linked (idempotent).
        Does not affect the ingredient entity itself.
        """
        recipe = await self._service.read(self._to_uuid6(uuid))
        if recipe is None:
            raise HTTPException(status_code = 404, detail = "Recipe not found")
        await self._service.remove_ingredient(self._to_uuid6(uuid), self._to_uuid6(ingredient_uuid))
