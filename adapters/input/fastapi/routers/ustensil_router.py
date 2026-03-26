from arclith.adapters.input.schemas import ApiResponse, success_response
from arclith.domain.ports.logger import Logger
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Annotated
from uuid import UUID as StdUUID
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
            prefix = "/v1/ustensils",
            tags = ["ustensils"],
            dependencies = [Depends(inject_tenant_uri)],
        )
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route(
            methods = ["POST"],
            path = "/",
            endpoint = self.create_ustensil,
            summary = "Create ustensil",
            response_model = ApiResponse[UstensilCreatedSchema],
            response_description = "UUID of the created ustensil",
            status_code = 201,
        )
        self.router.add_api_route(
            methods = ["GET"],
            path = "/",
            endpoint = self.list_ustensils,
            summary = "List ustensils",
            response_model = ApiResponse[list[UstensilSchema]],
            response_description = "List of active ustensils",
        )
        self.router.add_api_route(
            methods = ["DELETE"],
            path = "/purge",
            endpoint = self.purge_ustensils,
            summary = "Purge soft-deleted ustensils",
            response_model = ApiResponse[dict],
            response_description = "Number of permanently deleted records",
            status_code = 200,
        )
        self.router.add_api_route(
            methods = ["GET"],
            path = "/{uuid}",
            endpoint = self.get_ustensil,
            summary = "Get ustensil",
            response_model = ApiResponse[UstensilSchema],
            response_description = "The ustensil",
            responses = {404: {"description": "Ustensil not found"}},
        )
        self.router.add_api_route(
            methods = ["PUT"],
            path = "/{uuid}",
            endpoint = self.update_ustensil,
            summary = "Replace ustensil",
            status_code = 204,
            responses = {404: {"description": "Ustensil not found"}},
            response_model = None,
        )
        self.router.add_api_route(
            methods = ["PATCH"],
            path = "/{uuid}",
            endpoint = self.patch_ustensil,
            summary = "Partially update ustensil",
            status_code = 204,
            responses = {404: {"description": "Ustensil not found"}},
            response_model = None,
        )
        self.router.add_api_route(
            methods = ["DELETE"],
            path = "/{uuid}",
            endpoint = self.delete_ustensil,
            summary = "Delete ustensil",
            status_code = 204,
            response_model = None,
        )
        self.router.add_api_route(
            methods = ["POST"],
            path = "/{uuid}/duplicate",
            endpoint = self.duplicate_ustensil,
            summary = "Duplicate ustensil",
            response_model = ApiResponse[UstensilCreatedSchema],
            response_description = "UUID of the duplicated ustensil",
            status_code = 201,
        )

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    async def create_ustensil(self, payload: UstensilCreateSchema) -> ApiResponse[UstensilCreatedSchema]:
        """Create a new reusable ustensil."""
        result = await self._service.create(Ustensil(name = payload.name))
        return success_response(
            data = UstensilCreatedSchema(uuid = result.uuid),
            links = {
                "self": f"/v1/ustensils/{result.uuid}",
                "collection": "/v1/ustensils",
            },
        )

    async def get_ustensil(self, uuid: StdUUID) -> ApiResponse[UstensilSchema]:
        """Get an ustensil by its UUID."""
        result = await self._service.read(self._to_uuid6(uuid))
        if result is None:
            self._logger.warning("⚠️ Ustensil not found via HTTP", uuid = str(uuid))
            raise HTTPException(status_code = 404, detail = "Ustensil not found")
        return success_response(
            data = UstensilSchema.model_validate(result, from_attributes = True),
            links = {
                "self": f"/v1/ustensils/{uuid}",
                "collection": "/v1/ustensils",
                "duplicate": f"/v1/ustensils/{uuid}/duplicate",
            },
        )

    async def update_ustensil(self, uuid: StdUUID, payload: UstensilUpdateSchema) -> None:
        """Replace the name of an existing ustensil (PUT semantics)."""
        await self._service.update(Ustensil(uuid = self._to_uuid6(uuid), name = payload.name))

    async def patch_ustensil(self, uuid: StdUUID, payload: UstensilPatchSchema) -> None:
        """Partially update an ustensil (PATCH semantics)."""
        existing = await self._service.read(self._to_uuid6(uuid))
        if existing is None:
            self._logger.warning("⚠️ Ustensil not found for patching via HTTP", uuid = str(uuid))
            raise HTTPException(status_code = 404, detail = "Ustensil not found")
        await self._service.update(
            Ustensil(
                uuid = existing.uuid,
                name = payload.name if payload.name is not None else existing.name,
            )
        )

    async def delete_ustensil(self, uuid: StdUUID) -> None:
        """Soft-delete an ustensil."""
        await self._service.delete(self._to_uuid6(uuid))

    async def list_ustensils(
            self,
            name: Annotated[
                str | None,
                Query(min_length = 1,
                      description = "Filtre optionnel : recherche partielle sur le nom (insensible à la casse).",
                      examples = ["fouet"]),
            ] = None,
    ) -> ApiResponse[list[UstensilSchema]]:
        """List all active (non-deleted) ustensils."""
        items = await self._service.find_by_name(name) if name else await self._service.find_all()
        data = [UstensilSchema.model_validate(u, from_attributes = True) for u in items]
        return success_response(data = data, links = {"self": "/v1/ustensils"})

    async def duplicate_ustensil(self, uuid: StdUUID) -> ApiResponse[UstensilCreatedSchema]:
        """Duplicate an ustensil, assigning it a new UUID."""
        result = await self._service.duplicate(self._to_uuid6(uuid))
        return success_response(
            data = UstensilCreatedSchema(uuid = result.uuid),
            links = {
                "self": f"/v1/ustensils/{result.uuid}",
                "collection": "/v1/ustensils",
                "original": f"/v1/ustensils/{uuid}",
            },
        )

    async def purge_ustensils(self) -> ApiResponse[dict]:
        """Permanently delete soft-deleted ustensils that have exceeded the retention period."""
        purged = await self._service.purge()
        return success_response(data = {"purged": purged})
