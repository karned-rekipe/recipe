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
            response_model = list[UstensilSchema],
            response_description = "Ustensils linked to the recipe",
            status_code = 200,
            responses = {404: {"description": "Recipe not found"}},
        )
        self.router.add_api_route(
            methods = ["POST"],
            path = "/{ustensil_uuid}",
            endpoint = self.add_ustensil,
            summary = "Link ustensil to recipe",
            response_model = UstensilCreatedSchema,
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
        )

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    async def list_ustensils(self, uuid: StdUUID) -> list[UstensilSchema]:
        """List all ustensils currently linked to the recipe.

        Returns the snapshot data as stored in the recipe at link time.
        Each item: uuid, name, created_at, updated_at, version.
        """
        recipe = await self._service.read(self._to_uuid6(uuid))
        if recipe is None:
            self._logger.warning("⚠️ Recipe not found via HTTP", uuid = str(uuid))
            raise HTTPException(status_code = 404, detail = "Recipe not found")
        return [UstensilSchema.model_validate(u, from_attributes = True) for u in (recipe.ustensils or [])]

    async def add_ustensil(self, uuid: StdUUID, ustensil_uuid: StdUUID) -> UstensilCreatedSchema:
        """Link an existing ustensil to a recipe.

        Copies the ustensil's data (name, uuid) into the recipe at the time of linking.
        The original uuid is preserved to allow future synchronisation.
        Idempotent: if the ustensil is already linked, the call is silently ignored.
        Returns the UUID of the linked ustensil.
        """
        recipe = await self._service.read(self._to_uuid6(uuid))
        if recipe is None:
            raise HTTPException(status_code = 404, detail = "Recipe not found")
        try:
            await self._service.add_ustensil(self._to_uuid6(uuid), self._to_uuid6(ustensil_uuid))
        except ValueError as e:
            raise HTTPException(status_code = 404, detail = str(e))
        return UstensilCreatedSchema(uuid = ustensil_uuid)

    async def remove_ustensil(self, uuid: StdUUID, ustensil_uuid: StdUUID) -> None:
        """Unlink an ustensil from a recipe.

        Removes the ustensil snapshot from the recipe's ustensil list.
        Silent no-op if the ustensil is not currently linked (idempotent).
        Does not affect the ustensil entity itself.
        """
        recipe = await self._service.read(self._to_uuid6(uuid))
        if recipe is None:
            raise HTTPException(status_code = 404, detail = "Recipe not found")
        await self._service.remove_ustensil(self._to_uuid6(uuid), self._to_uuid6(ustensil_uuid))
