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
        self.router = APIRouter(prefix="/v1/recipes/{uuid}/steps", tags=["recipes"], dependencies=[Depends(inject_tenant_uri)])
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route("/", self.create_step, methods=["POST"], response_model=StepCreatedSchema, status_code=201)
        self.router.add_api_route("/", self.list_steps, methods=["GET"], response_model=list[StepSchema])
        self.router.add_api_route("/purge", self.purge_steps, methods=["DELETE"], status_code=200)
        self.router.add_api_route("/{uuid}", self.get_step, methods=["GET"], response_model=StepSchema)
        self.router.add_api_route("/{uuid}", self.update_step, methods=["PUT"], response_model=None, status_code=204)
        self.router.add_api_route("/{uuid}", self.patch_step, methods=["PATCH"], response_model=None, status_code=204)
        self.router.add_api_route("/{uuid}", self.delete_step, methods=["DELETE"], response_model=None, status_code=204)
        self.router.add_api_route("/{uuid}/duplicate", self.duplicate_step, methods=["POST"], response_model=StepCreatedSchema, status_code=201)

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    async def create_step(self, recipe_uuid: StdUUID, payload: StepCreateSchema) -> StepCreatedSchema:
        """Create a new step."""
        result = await self._service.create(Step(recipe_uuid=recipe_uuid, name=payload.name, description=payload.unit))
        return StepCreatedSchema(uuid=result.uuid)

    async def get_step(self, recipe_uuid: StdUUID, step_uuid: StdUUID) -> StepSchema:
        """Get an step by its UUID."""
        result = await self._service.read(self._to_uuid6(step_uuid))
        if result is None:
            self._logger.warning("⚠️ Step not found via HTTP", uuid=str(uuid))
            raise HTTPException(status_code=404, detail="Step not found")
        return StepSchema.model_validate(result, from_attributes=True)

    async def update_step(self, uuid: StdUUID, payload: StepUpdateSchema) -> None:
        """Update an existing step."""
        await self._service.update(Step(uuid=self._to_uuid6(uuid), name=payload.name, unit=payload.unit))

    async def patch_step(self, uuid: StdUUID, payload: StepPatchSchema) -> None:
        """Partially update an step."""
        existing = await self._service.read(self._to_uuid6(uuid))
        if existing is None:
            self._logger.warning("⚠️ Step not found via HTTP", uuid=str(uuid))
            raise HTTPException(status_code=404, detail="Step not found")
        await self._service.update(Step(
            uuid=existing.uuid,
            name=payload.name if payload.name is not None else existing.name,
            unit=payload.unit if payload.unit is not None else existing.unit,
        ))


    async def delete_step(self, uuid: StdUUID) -> None:
        """Delete an step by its UUID."""
        await self._service.delete(self._to_uuid6(uuid))

    async def list_steps(
        self,
        name: str | None = Query(
            default=None,
            min_length=1,
            description="Filtre par nom (recherche partielle, insensible à la casse).",
            examples=["farine"],
        ),
    ) -> list[StepSchema]:
        """List all steps, optionally filtered by name."""
        items = await self._service.find_by_name(name) if name else await self._service.find_all()
        return [StepSchema.model_validate(i) for i in items]

    async def duplicate_step(self, uuid: StdUUID) -> StepCreatedSchema:
        """Duplicate an step, assigning it a new UUID."""
        result = await self._service.duplicate(self._to_uuid6(uuid))
        return StepCreatedSchema(uuid=result.uuid)

    async def purge_steps(self) -> dict:
        """Purge all soft-deleted steps that have exceeded the retention period."""
        purged = await self._service.purge()
        return {"purged": purged}

