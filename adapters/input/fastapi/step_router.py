from typing import Annotated
from uuid import UUID as StdUUID

from arclith.domain.ports.logger import Logger
from fastapi import APIRouter, Depends, HTTPException, Query
from uuid6 import UUID

from adapters.input.fastapi.dependencies import inject_tenant_uri
from adapters.input.schemas.step_schema import (
    StepCreateSchema,
    StepCreatedSchema,
    StepPatchSchema,
    StepSchema,
    StepUpdateSchema,
)
from application.services.step_service import StepService
from domain.models.step import Step


class StepRouter:
    def __init__(self, service: StepService, logger: Logger) -> None:
        self._service = service
        self._logger = logger
        self.router = APIRouter(prefix = "/v1/recipes/{uuid}/steps", tags = ["recipes : steps"],
                                dependencies = [Depends(inject_tenant_uri)])
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route("/", self.create_step, methods = ["POST"], response_model = StepCreatedSchema,
                                  status_code = 201,
                                  summary = "Create step", response_description = "UUID of the created step")
        self.router.add_api_route("/", self.list_steps, methods = ["GET"], response_model = list[StepSchema],
                                  summary = "List steps for recipe",
                                  response_description = "Steps of the recipe in creation order")
        self.router.add_api_route("/purge", self.purge_steps, methods = ["DELETE"], status_code = 200,
                                  summary = "Purge soft-deleted steps",
                                  response_description = "Number of permanently deleted records")
        self.router.add_api_route("/{step_uuid}", self.get_step, methods = ["GET"], response_model = StepSchema,
                                  summary = "Get step", response_description = "The step",
                                  responses = {404: {"description": "Step not found"}})
        self.router.add_api_route("/{step_uuid}", self.update_step, methods = ["PUT"], response_model = None,
                                  status_code = 204,
                                  summary = "Replace step", responses = {404: {"description": "Step not found"}})
        self.router.add_api_route("/{step_uuid}", self.patch_step, methods = ["PATCH"], response_model = None,
                                  status_code = 204,
                                  summary = "Partially update step",
                                  responses = {404: {"description": "Step not found"}})
        self.router.add_api_route("/{step_uuid}", self.delete_step, methods = ["DELETE"], response_model = None,
                                  status_code = 204,
                                  summary = "Delete step", responses = {404: {"description": "Step not found"}})
        self.router.add_api_route("/{step_uuid}/duplicate", self.duplicate_step, methods = ["POST"],
                                  response_model = StepCreatedSchema, status_code = 201,
                                  summary = "Duplicate step", response_description = "UUID of the duplicated step",
                                  responses = {404: {"description": "Step not found"}})

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    async def create_step(self, uuid: StdUUID, payload: StepCreateSchema) -> StepCreatedSchema:
        """Create a new step linked to the recipe.

        Steps define the preparation procedure of a recipe in chronological order.
        Returns the UUID of the created step.
        Fields: uuid, recipe_uuid, name, description, created_at, updated_at, version.
        """
        result = await self._service.create(Step(
            recipe_uuid = self._to_uuid6(uuid),
            name=payload.name,
            description=payload.description,
        ))
        return StepCreatedSchema(uuid=result.uuid)

    async def get_step(self, uuid: StdUUID, step_uuid: StdUUID) -> StepSchema:
        """Get a step by its UUID, scoped to the given recipe.

        Returns 404 if the step does not exist or does not belong to the specified recipe.
        Fields: uuid, recipe_uuid, name, description, created_at, updated_at, version.
        """
        result = await self._service.read(self._to_uuid6(step_uuid))
        if result is None or result.recipe_uuid != self._to_uuid6(uuid):
            self._logger.warning("⚠️ Step not found via HTTP", step_uuid = str(step_uuid), recipe_uuid = str(uuid))
            raise HTTPException(status_code=404, detail="Step not found")
        return StepSchema.model_validate(result, from_attributes=True)

    async def update_step(self, uuid: StdUUID, step_uuid: StdUUID, payload: StepUpdateSchema) -> None:
        """Replace name and description of a step (PUT semantics), scoped to the given recipe.

        Returns 404 if the step does not exist or does not belong to the specified recipe.
        """
        existing = await self._service.read(self._to_uuid6(step_uuid))
        if existing is None or existing.recipe_uuid != self._to_uuid6(uuid):
            self._logger.warning("⚠️ Step not found via HTTP", step_uuid = str(step_uuid), recipe_uuid = str(uuid))
            raise HTTPException(status_code=404, detail="Step not found")
        await self._service.update(Step(
            uuid=existing.uuid,
            recipe_uuid=existing.recipe_uuid,
            name=payload.name,
            description=payload.description,
        ))

    async def patch_step(self, uuid: StdUUID, step_uuid: StdUUID, payload: StepPatchSchema) -> None:
        """Partially update a step (PATCH semantics), scoped to the given recipe.

        Only the fields provided in the body are updated; omitted fields keep their current value.
        Returns 404 if the step does not exist or does not belong to the specified recipe.
        """
        existing = await self._service.read(self._to_uuid6(step_uuid))
        if existing is None or existing.recipe_uuid != self._to_uuid6(uuid):
            self._logger.warning("⚠️ Step not found via HTTP", step_uuid = str(step_uuid), recipe_uuid = str(uuid))
            raise HTTPException(status_code=404, detail="Step not found")
        await self._service.update(Step(
            uuid=existing.uuid,
            recipe_uuid=existing.recipe_uuid,
            name=payload.name if payload.name is not None else existing.name,
            description=payload.description if payload.description is not None else existing.description,
        ))

    async def delete_step(self, uuid: StdUUID, step_uuid: StdUUID) -> None:
        """Soft-delete a step, scoped to the given recipe.

        The step is marked as deleted and excluded from list results.
        Returns 404 if the step does not exist or does not belong to the specified recipe.
        Use `DELETE /v1/recipes/{uuid}/steps/purge` to permanently remove expired entries.
        """
        existing = await self._service.read(self._to_uuid6(step_uuid))
        if existing is None or existing.recipe_uuid != self._to_uuid6(uuid):
            self._logger.warning("⚠️ Step not found via HTTP", step_uuid = str(step_uuid), recipe_uuid = str(uuid))
            raise HTTPException(status_code=404, detail="Step not found")
        await self._service.delete(self._to_uuid6(step_uuid))

    async def list_steps(
        self,
            uuid: StdUUID,
            name: Annotated[str | None, Query(
            min_length=1,
                description = "Filtre optionnel : recherche partielle sur le nom, insensible à la casse.",
            examples=["préparer"],
            )] = None,
    ) -> list[StepSchema]:
        """List all steps belonging to the recipe, optionally filtered by name.

        Returns steps in creation order (UUIDv7 time-ordered).
        Each item: uuid, recipe_uuid, name, description, created_at, updated_at, version.
        """
        items = await self._service.find_by_recipe(self._to_uuid6(uuid))
        if name:
            name_lower = name.lower()
            items = [i for i in items if name_lower in i.name.lower()]
        return [StepSchema.model_validate(i, from_attributes=True) for i in items]

    async def duplicate_step(self, uuid: StdUUID, step_uuid: StdUUID) -> StepCreatedSchema:
        """Duplicate a step, assigning it a new UUID, scoped to the given recipe.

        The copy remains linked to the same recipe.
        Returns the UUID of the new step.
        Returns 404 if the step does not exist or does not belong to the specified recipe.
        """
        existing = await self._service.read(self._to_uuid6(step_uuid))
        if existing is None or existing.recipe_uuid != self._to_uuid6(uuid):
            self._logger.warning("⚠️ Step not found via HTTP", step_uuid = str(step_uuid), recipe_uuid = str(uuid))
            raise HTTPException(status_code=404, detail="Step not found")
        result = await self._service.duplicate(self._to_uuid6(step_uuid))
        return StepCreatedSchema(uuid=result.uuid)

    async def purge_steps(self, uuid: StdUUID) -> dict:
        """Permanently delete soft-deleted steps that have exceeded the retention period.

        Returns {"purged": <count>} with the number of permanently deleted records.
        This operation is irreversible.
        """
        purged = await self._service.purge()
        return {"purged": purged}
