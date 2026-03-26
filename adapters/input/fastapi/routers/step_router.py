from arclith.adapters.input.schemas import ApiResponse, success_response
from arclith.domain.ports.logger import Logger
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Annotated
from uuid import UUID as StdUUID
from uuid6 import UUID

from adapters.input.fastapi.dependencies import inject_tenant_uri
from adapters.input.schemas.step_schema import (
    StepCreateSchema,
    StepCreatedSchema,
    StepPatchSchema,
    StepSchema,
    StepUpdateSchema,
)
from application.services.recipe_service import RecipeService
from application.services.step_service import StepService
from domain.models.step import Step


class StepRouter:
    def __init__(self, service: StepService, recipe_service: RecipeService, logger: Logger) -> None:
        self._service = service
        self._recipe_service = recipe_service
        self._logger = logger
        self.router = APIRouter(
            prefix = "/v1/recipes/{uuid}/steps",
            tags = ["recipes : steps"],
            dependencies = [Depends(inject_tenant_uri)],
        )
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route(
            methods = ["POST"],
            path = "/",
            endpoint = self.create_step,
            summary = "Create step",
            response_model = ApiResponse[StepCreatedSchema],
            response_description = "UUID of the created step",
            status_code = 201,
            responses = {404: {"description": "Recipe not found"}},
        )
        self.router.add_api_route(
            methods = ["GET"],
            path = "/",
            endpoint = self.list_steps,
            summary = "List steps for recipe",
            response_model = ApiResponse[list[StepSchema]],
            response_description = "Steps of the recipe in creation order",
            responses = {404: {"description": "Recipe not found"}},
        )
        self.router.add_api_route(
            methods = ["DELETE"],
            path = "/purge",
            endpoint = self.purge_steps,
            summary = "Purge soft-deleted steps",
            response_model = ApiResponse[dict],
            response_description = "Number of permanently deleted records",
            status_code = 200,
        )
        self.router.add_api_route(
            methods = ["GET"],
            path = "/{step_uuid}",
            endpoint = self.get_step,
            summary = "Get step",
            response_model = ApiResponse[StepSchema],
            response_description = "The step",
            responses = {404: {"description": "Step not found"}},
        )
        self.router.add_api_route(
            methods = ["PUT"],
            path = "/{step_uuid}",
            endpoint = self.update_step,
            summary = "Replace step",
            status_code = 204,
            responses = {404: {"description": "Step not found"}},
            response_model = None,
        )
        self.router.add_api_route(
            methods = ["PATCH"],
            path = "/{step_uuid}",
            endpoint = self.patch_step,
            summary = "Partially update step",
            status_code = 204,
            responses = {404: {"description": "Step not found"}},
            response_model = None,
        )
        self.router.add_api_route(
            methods = ["DELETE"],
            path = "/{step_uuid}",
            endpoint = self.delete_step,
            summary = "Delete step",
            status_code = 204,
            responses = {404: {"description": "Step not found"}},
            response_model = None,
        )
        self.router.add_api_route(
            methods = ["POST"],
            path = "/{step_uuid}/duplicate",
            endpoint = self.duplicate_step,
            summary = "Duplicate step",
            response_model = ApiResponse[StepCreatedSchema],
            response_description = "UUID of the duplicated step",
            status_code = 201,
            responses = {404: {"description": "Step not found"}},
        )

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    async def create_step(self, uuid: StdUUID, payload: StepCreateSchema) -> ApiResponse[StepCreatedSchema]:
        """Create a new step linked to the recipe."""
        recipe = await self._recipe_service.read(self._to_uuid6(uuid))
        if recipe is None:
            self._logger.warning("⚠️ Recipe not found via HTTP", uuid = str(uuid))
            raise HTTPException(status_code = 404, detail = "Recipe not found")
        result = await self._service.create(Step(
            recipe_uuid = self._to_uuid6(uuid),
            name = payload.name,
            description = payload.description,
        ))
        return success_response(
            data = StepCreatedSchema(uuid = result.uuid),
            links = {
                "self": f"/v1/recipes/{uuid}/steps/{result.uuid}",
                "collection": f"/v1/recipes/{uuid}/steps",
            },
        )

    async def get_step(self, uuid: StdUUID, step_uuid: StdUUID) -> ApiResponse[StepSchema]:
        """Get a step by its UUID, scoped to the given recipe."""
        result = await self._service.read(self._to_uuid6(step_uuid))
        if result is None or result.recipe_uuid != self._to_uuid6(uuid):
            self._logger.warning("⚠️ Step not found via HTTP", step_uuid = str(step_uuid), recipe_uuid = str(uuid))
            raise HTTPException(status_code = 404, detail = "Step not found")
        return success_response(
            data = StepSchema.model_validate(result, from_attributes = True),
            links = {
                "self": f"/v1/recipes/{uuid}/steps/{step_uuid}",
                "collection": f"/v1/recipes/{uuid}/steps",
                "duplicate": f"/v1/recipes/{uuid}/steps/{step_uuid}/duplicate",
            },
        )

    async def list_steps(
            self,
            uuid: StdUUID,
            name: Annotated[str | None, Query(
                min_length = 1,
                description = "Filtre optionnel : recherche partielle sur le nom (insensible à la casse).",
                examples = ["préparer"],
            )] = None,
    ) -> ApiResponse[list[StepSchema]]:
        """List all steps belonging to the recipe, optionally filtered by name."""
        recipe = await self._recipe_service.read(self._to_uuid6(uuid))
        if recipe is None:
            self._logger.warning("⚠️ Recipe not found via HTTP", uuid = str(uuid))
            raise HTTPException(status_code = 404, detail = "Recipe not found")
        items = await self._service.find_by_recipe(self._to_uuid6(uuid))
        if name:
            name_lower = name.lower()
            items = [i for i in items if name_lower in i.name.lower()]
        data = [StepSchema.model_validate(i, from_attributes = True) for i in items]
        return success_response(data = data, links = {"self": f"/v1/recipes/{uuid}/steps"})

    async def update_step(self, uuid: StdUUID, step_uuid: StdUUID, payload: StepUpdateSchema) -> None:
        """Replace name and description of a step (PUT semantics)."""
        existing = await self._service.read(self._to_uuid6(step_uuid))
        if existing is None or existing.recipe_uuid != self._to_uuid6(uuid):
            self._logger.warning("⚠️ Step not found via HTTP", step_uuid = str(step_uuid), recipe_uuid = str(uuid))
            raise HTTPException(status_code = 404, detail = "Step not found")
        await self._service.update(Step(
            uuid = existing.uuid,
            recipe_uuid = existing.recipe_uuid,
            name = payload.name,
            description = payload.description,
        ))

    async def patch_step(self, uuid: StdUUID, step_uuid: StdUUID, payload: StepPatchSchema) -> None:
        """Partially update a step (PATCH semantics)."""
        existing = await self._service.read(self._to_uuid6(step_uuid))
        if existing is None or existing.recipe_uuid != self._to_uuid6(uuid):
            self._logger.warning("⚠️ Step not found via HTTP", step_uuid = str(step_uuid), recipe_uuid = str(uuid))
            raise HTTPException(status_code = 404, detail = "Step not found")
        await self._service.update(Step(
            uuid = existing.uuid,
            recipe_uuid = existing.recipe_uuid,
            name = payload.name if payload.name is not None else existing.name,
            description = payload.description if payload.description is not None else existing.description,
        ))

    async def delete_step(self, uuid: StdUUID, step_uuid: StdUUID) -> None:
        """Soft-delete a step."""
        existing = await self._service.read(self._to_uuid6(step_uuid))
        if existing is None or existing.recipe_uuid != self._to_uuid6(uuid):
            self._logger.warning("⚠️ Step not found via HTTP", step_uuid = str(step_uuid), recipe_uuid = str(uuid))
            raise HTTPException(status_code = 404, detail = "Step not found")
        await self._service.delete(self._to_uuid6(step_uuid))

    async def duplicate_step(self, uuid: StdUUID, step_uuid: StdUUID) -> ApiResponse[StepCreatedSchema]:
        """Duplicate a step, assigning it a new UUID."""
        existing = await self._service.read(self._to_uuid6(step_uuid))
        if existing is None or existing.recipe_uuid != self._to_uuid6(uuid):
            self._logger.warning("⚠️ Step not found via HTTP", step_uuid = str(step_uuid), recipe_uuid = str(uuid))
            raise HTTPException(status_code = 404, detail = "Step not found")
        result = await self._service.duplicate(self._to_uuid6(step_uuid))
        return success_response(
            data = StepCreatedSchema(uuid = result.uuid),
            links = {
                "self": f"/v1/recipes/{uuid}/steps/{result.uuid}",
                "collection": f"/v1/recipes/{uuid}/steps",
                "original": f"/v1/recipes/{uuid}/steps/{step_uuid}",
            },
        )

    async def purge_steps(self, uuid: StdUUID) -> ApiResponse[dict]:
        """Permanently delete soft-deleted steps that have exceeded the retention period."""
        purged = await self._service.purge()
        return success_response(data = {"purged": purged})
