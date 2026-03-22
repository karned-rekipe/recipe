from uuid import UUID as StdUUID

from arclith.domain.ports.logger import Logger
from fastapi import APIRouter, Depends, HTTPException
from uuid6 import UUID

from adapters.input.fastapi.dependencies import inject_tenant_uri
from adapters.input.schemas.ustensil_schema import UstensilCreatedSchema
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
        self.router.add_api_route("/{ustensil_uuid}", self.add_ustensil, methods = ["POST"],
                                  response_model = UstensilCreatedSchema, status_code = 201,
                                  summary = "Link ustensil to recipe",
                                  response_description = "UUID of the linked ustensil",
                                  responses = {404: {"description": "Recipe or ustensil not found"}})
        self.router.add_api_route("/{ustensil_uuid}", self.remove_ustensil, methods = ["DELETE"],
                                  response_model = None, status_code = 204,
                                  summary = "Unlink ustensil from recipe")

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

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
