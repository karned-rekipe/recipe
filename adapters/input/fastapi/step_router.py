from uuid import UUID as StdUUID

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
from arclith.domain.ports.logger import Logger
from domain.models.step import Step


class StepRouter:
    def __init__(self, service: StepService, logger: Logger) -> None:
        self._service = service
        self._logger = logger
        self.router = APIRouter(prefix="/v1/recipes/{recipe_uuid}/steps", tags=["steps"], dependencies=[Depends(inject_tenant_uri)])
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route("/", self.create_step, methods=["POST"], response_model=StepCreatedSchema, status_code=201)
        self.router.add_api_route("/", self.list_steps, methods=["GET"], response_model=list[StepSchema])
        self.router.add_api_route("/purge", self.purge_steps, methods=["DELETE"], status_code=200)
        self.router.add_api_route("/{step_uuid}", self.get_step, methods=["GET"], response_model=StepSchema)
        self.router.add_api_route("/{step_uuid}", self.update_step, methods=["PUT"], response_model=None, status_code=204)
        self.router.add_api_route("/{step_uuid}", self.patch_step, methods=["PATCH"], response_model=None, status_code=204)
        self.router.add_api_route("/{step_uuid}", self.delete_step, methods=["DELETE"], response_model=None, status_code=204)
        self.router.add_api_route("/{step_uuid}/duplicate", self.duplicate_step, methods=["POST"], response_model=StepCreatedSchema, status_code=201)

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    async def create_step(self, recipe_uuid: StdUUID, payload: StepCreateSchema) -> StepCreatedSchema:
        """Create a new step linked to the given recipe."""
        result = await self._service.create(Step(
            recipe_uuid=self._to_uuid6(recipe_uuid),
            name=payload.name,
            description=payload.description,
        ))
        return StepCreatedSchema(uuid=result.uuid)

    async def get_step(self, recipe_uuid: StdUUID, step_uuid: StdUUID) -> StepSchema:
        """Get a step by its UUID, scoped to the given recipe."""
        result = await self._service.read(self._to_uuid6(step_uuid))
        if result is None or result.recipe_uuid != self._to_uuid6(recipe_uuid):
            self._logger.warning("⚠️ Step not found via HTTP", step_uuid=str(step_uuid), recipe_uuid=str(recipe_uuid))
            raise HTTPException(status_code=404, detail="Step not found")
        return StepSchema.model_validate(result, from_attributes=True)

    async def update_step(self, recipe_uuid: StdUUID, step_uuid: StdUUID, payload: StepUpdateSchema) -> None:
        """Update an existing step, scoped to the given recipe."""
        existing = await self._service.read(self._to_uuid6(step_uuid))
        if existing is None or existing.recipe_uuid != self._to_uuid6(recipe_uuid):
            self._logger.warning("⚠️ Step not found via HTTP", step_uuid=str(step_uuid), recipe_uuid=str(recipe_uuid))
            raise HTTPException(status_code=404, detail="Step not found")
        await self._service.update(Step(
            uuid=existing.uuid,
            recipe_uuid=existing.recipe_uuid,
            name=payload.name,
            description=payload.description,
        ))

    async def patch_step(self, recipe_uuid: StdUUID, step_uuid: StdUUID, payload: StepPatchSchema) -> None:
        """Partially update a step, scoped to the given recipe."""
        existing = await self._service.read(self._to_uuid6(step_uuid))
        if existing is None or existing.recipe_uuid != self._to_uuid6(recipe_uuid):
            self._logger.warning("⚠️ Step not found via HTTP", step_uuid=str(step_uuid), recipe_uuid=str(recipe_uuid))
            raise HTTPException(status_code=404, detail="Step not found")
        await self._service.update(Step(
            uuid=existing.uuid,
            recipe_uuid=existing.recipe_uuid,
            name=payload.name if payload.name is not None else existing.name,
            description=payload.description if payload.description is not None else existing.description,
        ))

    async def delete_step(self, recipe_uuid: StdUUID, step_uuid: StdUUID) -> None:
        """Delete a step by its UUID, scoped to the given recipe."""
        existing = await self._service.read(self._to_uuid6(step_uuid))
        if existing is None or existing.recipe_uuid != self._to_uuid6(recipe_uuid):
            self._logger.warning("⚠️ Step not found via HTTP", step_uuid=str(step_uuid), recipe_uuid=str(recipe_uuid))
            raise HTTPException(status_code=404, detail="Step not found")
        await self._service.delete(self._to_uuid6(step_uuid))

    async def list_steps(
        self,
        recipe_uuid: StdUUID,
        name: str | None = Query(
            default=None,
            min_length=1,
            description="Filtre par nom (recherche partielle, insensible à la casse).",
            examples=["préparer"],
        ),
    ) -> list[StepSchema]:
        """List all steps for the given recipe, optionally filtered by name."""
        items = await self._service.find_by_recipe(self._to_uuid6(recipe_uuid))
        if name:
            name_lower = name.lower()
            items = [i for i in items if name_lower in i.name.lower()]
        return [StepSchema.model_validate(i, from_attributes=True) for i in items]

    async def duplicate_step(self, recipe_uuid: StdUUID, step_uuid: StdUUID) -> StepCreatedSchema:
        """Duplicate a step, assigning it a new UUID, scoped to the given recipe."""
        existing = await self._service.read(self._to_uuid6(step_uuid))
        if existing is None or existing.recipe_uuid != self._to_uuid6(recipe_uuid):
            self._logger.warning("⚠️ Step not found via HTTP", step_uuid=str(step_uuid), recipe_uuid=str(recipe_uuid))
            raise HTTPException(status_code=404, detail="Step not found")
        result = await self._service.duplicate(self._to_uuid6(step_uuid))
        return StepCreatedSchema(uuid=result.uuid)

    async def purge_steps(self, recipe_uuid: StdUUID) -> dict:
        """Purge all soft-deleted steps that have exceeded the retention period."""
        purged = await self._service.purge()
        return {"purged": purged}

