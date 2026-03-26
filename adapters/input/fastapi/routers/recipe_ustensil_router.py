from arclith.adapters.input.schemas import ApiResponse, success_response
from arclith.domain.ports.logger import Logger
from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID as StdUUID
from uuid6 import UUID

from adapters.input.fastapi.dependencies import inject_tenant_uri
from adapters.input.schemas.ustensil_schema import UstensilCreatedSchema, UstensilSchema
from application.services.recipe_service import RecipeService


class RecipeUstensilRouter:
    def __init__(self, service: RecipeService, logger: Logger) -> None:
        self._service = service
        self._logger = logger
        self.router = APIRouter(
            prefix = "/v1/recipes/{uuid}/ustensils",
            tags = ["recipes : ustensils"],
            dependencies = [Depends(inject_tenant_uri)],
        )
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route(
            methods = ["GET"],
            path = "/",
            endpoint = self.list_ustensils,
            summary = "List recipe ustensils",
            response_model = ApiResponse[list[UstensilSchema]],
            response_description = "Ustensils linked to the recipe",
            responses = {404: {"description": "Recipe not found"}},
        )
        self.router.add_api_route(
            methods = ["POST"],
            path = "/{ustensil_uuid}",
            endpoint = self.add_ustensil,
            summary = "Link ustensil to recipe",
            response_model = ApiResponse[UstensilCreatedSchema],
            response_description = "UUID of the linked ustensil",
            status_code = 201,
            responses = {404: {"description": "Recipe or ustensil not found"}},
        )
        self.router.add_api_route(
            methods = ["DELETE"],
            path = "/{ustensil_uuid}",
            endpoint = self.remove_ustensil,
            summary = "Unlink ustensil from recipe",
            status_code = 204,
            response_model = None,
        )

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    async def list_ustensils(self, uuid: StdUUID) -> ApiResponse[list[UstensilSchema]]:
        """List all ustensils currently linked to the recipe."""
        recipe = await self._service.read(self._to_uuid6(uuid))
        if recipe is None:
            self._logger.warning("⚠️ Recipe not found via HTTP", uuid = str(uuid))
            raise HTTPException(status_code = 404, detail = "Recipe not found")
        data = [UstensilSchema.model_validate(u, from_attributes = True) for u in (recipe.ustensils or [])]
        return success_response(
            data = data,
            links = {"self": f"/v1/recipes/{uuid}/ustensils"},
        )

    async def add_ustensil(self, uuid: StdUUID, ustensil_uuid: StdUUID) -> ApiResponse[UstensilCreatedSchema]:
        """Link an existing ustensil to a recipe."""
        recipe = await self._service.read(self._to_uuid6(uuid))
        if recipe is None:
            raise HTTPException(status_code = 404, detail = "Recipe not found")
        try:
            await self._service.add_ustensil(self._to_uuid6(uuid), self._to_uuid6(ustensil_uuid))
        except ValueError as e:
            raise HTTPException(status_code = 404, detail = str(e))
        return success_response(
            data = UstensilCreatedSchema(uuid = ustensil_uuid),
            links = {
                "self": f"/v1/recipes/{uuid}/ustensils/{ustensil_uuid}",
                "collection": f"/v1/recipes/{uuid}/ustensils",
                "ustensil": f"/v1/ustensils/{ustensil_uuid}",
            },
        )

    async def remove_ustensil(self, uuid: StdUUID, ustensil_uuid: StdUUID) -> None:
        """Unlink an ustensil from a recipe."""
        recipe = await self._service.read(self._to_uuid6(uuid))
        if recipe is None:
            raise HTTPException(status_code = 404, detail = "Recipe not found")
        await self._service.remove_ustensil(self._to_uuid6(uuid), self._to_uuid6(ustensil_uuid))
