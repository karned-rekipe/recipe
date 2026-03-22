from uuid import UUID as StdUUID

from arclith.domain.ports.logger import Logger
from fastapi import APIRouter, Depends, HTTPException
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
        self.router.add_api_route("/", self.list_ingredients, methods = ["GET"],
                                  response_model = list[IngredientSchema], status_code = 200,
                                  summary = "List recipe ingredients",
                                  response_description = "Ingredients linked to the recipe",
                                  responses = {404: {"description": "Recipe not found"}})
        self.router.add_api_route("/{ingredient_uuid}", self.add_ingredient, methods = ["POST"],
                                  response_model = IngredientCreatedSchema, status_code = 201,
                                  summary = "Link ingredient to recipe",
                                  response_description = "UUID of the linked ingredient",
                                  responses = {404: {"description": "Recipe or ingredient not found"}})
        self.router.add_api_route("/{ingredient_uuid}", self.remove_ingredient, methods = ["DELETE"],
                                  response_model = None, status_code = 204,
                                  summary = "Unlink ingredient from recipe")

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
