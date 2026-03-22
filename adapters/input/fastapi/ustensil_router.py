from typing import Annotated
from uuid import UUID as StdUUID

from arclith.domain.ports.logger import Logger
from fastapi import APIRouter, Depends, HTTPException, Query
from uuid6 import UUID

from adapters.input.fastapi.dependencies import inject_tenant_uri
from adapters.input.schemas.ustensil_schema import (
    UstensilCreateSchema,
    UstensilCreatedSchema,
    UstensilPatchSchema,
    UstensilSchema,
    UstensilUpdateSchema,
)
from application.services.ustensil_service import UstensilService
from domain.models.ustensil import Ustensil


class UstensilRouter:
    def __init__(self, service: UstensilService, logger: Logger) -> None:
        self._service = service
        self._logger = logger
        self.router = APIRouter(
            prefix="/v1/ustensils",
            tags=["ustensils"],
            dependencies=[Depends(inject_tenant_uri)]
        )
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route("/", self.create_ustensil, methods = ["POST"], response_model = UstensilCreatedSchema,
                                  status_code = 201,
                                  summary = "Create ustensil", response_description = "UUID of the created ustensil")
        self.router.add_api_route("/", self.list_ustensils, methods = ["GET"], response_model = list[UstensilSchema],
                                  status_code = 200,
                                  summary = "List ustensils", response_description = "List of active ustensils")
        self.router.add_api_route("/purge", self.purge_ustensils, methods = ["DELETE"], response_model = dict,
                                  status_code = 200,
                                  summary = "Purge soft-deleted ustensils",
                                  response_description = "Number of permanently deleted records")
        self.router.add_api_route("/{uuid}", self.get_ustensil, methods = ["GET"], response_model = UstensilSchema,
                                  status_code = 200,
                                  summary = "Get ustensil", response_description = "The ustensil",
                                  responses = {404: {"description": "Ustensil not found"}})
        self.router.add_api_route("/{uuid}", self.update_ustensil, methods = ["PUT"], response_model = None,
                                  status_code = 204,
                                  summary = "Replace ustensil",
                                  responses = {404: {"description": "Ustensil not found"}})
        self.router.add_api_route("/{uuid}", self.patch_ustensil, methods = ["PATCH"], response_model = None,
                                  status_code = 204,
                                  summary = "Partially update ustensil",
                                  responses = {404: {"description": "Ustensil not found"}})
        self.router.add_api_route("/{uuid}", self.delete_ustensil, methods = ["DELETE"], response_model = None,
                                  status_code = 204,
                                  summary = "Delete ustensil")
        self.router.add_api_route("/{uuid}/duplicate", self.duplicate_ustensil, methods = ["POST"],
                                  response_model = UstensilCreatedSchema, status_code = 201,
                                  summary = "Duplicate ustensil",
                                  response_description = "UUID of the duplicated ustensil")

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    async def create_ustensil(self, payload: UstensilCreateSchema) -> UstensilCreatedSchema:
        """Create a new reusable ustensil.

        Returns the UUID of the created ustensil.
        Once created, use `POST /v1/recipes/{uuid}/ustensils/{ustensil_uuid}` to attach it to a recipe.
        """
        result = await self._service.create(Ustensil(name=payload.name))
        return UstensilCreatedSchema(uuid=result.uuid)

    async def get_ustensil(self, uuid: StdUUID) -> UstensilSchema:
        """Get an ustensil by its UUID.

        Returns the full ustensil object.
        Fields: uuid, name, created_at, updated_at, version.
        """
        result = await self._service.read(self._to_uuid6(uuid))
        if result is None:
            self._logger.warning("⚠️ Ustensil not found via HTTP", uuid=str(uuid))
            raise HTTPException(status_code=404, detail="Ustensil not found")
        return UstensilSchema.model_validate(result, from_attributes = True)

    async def list_ustensils(
            self,
            name: Annotated[str | None, Query(
                min_length = 1,
                description = "Filtre optionnel : recherche partielle sur le nom, insensible à la casse. Ex: 'fou' retournera 'Fouet'.",
                examples = ["Fouet"],
            )] = None,
    ) -> list[UstensilSchema]:
        """List all active (non-deleted) ustensils.

        Pass `name` for a partial, case-insensitive name filter.
        Each item: uuid, name, created_at, updated_at, version.
        Use the returned UUIDs with `POST /v1/recipes/{uuid}/ustensils/{ustensil_uuid}` to link them to a recipe.
        """
        items = await self._service.find_by_name(name) if name else await self._service.find_all()
        return [UstensilSchema.model_validate(u, from_attributes = True) for u in items]

    async def update_ustensil(self, uuid: StdUUID, payload: UstensilUpdateSchema) -> None:
        """Replace the name of an existing ustensil (PUT semantics).

        Note: changes do not propagate to recipes where this ustensil is already linked (snapshot model).
        """
        await self._service.update(Ustensil(uuid=self._to_uuid6(uuid), name=payload.name))

    async def patch_ustensil(self, uuid: StdUUID, payload: UstensilPatchSchema) -> None:
        """Partially update an ustensil (PATCH semantics).

        Only the fields provided in the body are updated; omitted fields keep their current value.
        Note: changes do not propagate to recipes where this ustensil is already linked (snapshot model).
        """
        existing = await self._service.read(self._to_uuid6(uuid))
        if existing is None:
            self._logger.warning("⚠️ Ustensil not found for patching via HTTP", uuid=str(uuid))
            raise HTTPException(status_code=404, detail="Ustensil not found")
        await self._service.update(Ustensil(
            uuid=self._to_uuid6(uuid),
            name=payload.name if payload.name is not None else existing.name
        ))

    async def delete_ustensil(self, uuid: StdUUID) -> None:
        """Soft-delete an ustensil.

        The ustensil is marked as deleted and excluded from list results.
        It is retained until the purge retention period expires.
        Use `DELETE /v1/ustensils/purge` to permanently remove expired entries.
        """
        await self._service.delete(self._to_uuid6(uuid))

    async def purge_ustensils(self) -> dict:
        """Permanently delete soft-deleted ustensils that have exceeded the retention period.

        Returns {"purged": <count>} with the number of permanently deleted records.
        This operation is irreversible.
        """
        purged = await self._service.purge()
        return {"purged": purged}

    async def duplicate_ustensil(self, uuid: StdUUID) -> UstensilCreatedSchema:
        """Duplicate an ustensil, assigning it a new UUID.

        Creates an independent copy with the same name.
        Returns the UUID of the new ustensil.
        """
        result = await self._service.duplicate(self._to_uuid6(uuid))
        return UstensilCreatedSchema(uuid = result.uuid)
