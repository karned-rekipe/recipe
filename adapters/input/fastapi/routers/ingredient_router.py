from arclith.adapters.input.schemas import ApiResponse, success_response
from arclith.domain.ports.logger import Logger
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Annotated
from uuid import UUID as StdUUID
from uuid6 import UUID

from adapters.input.fastapi.dependencies import inject_tenant_uri
from adapters.input.schemas.ingredient_schema import (
    IngredientCreateSchema,
    IngredientCreatedSchema,
    IngredientPatchSchema,
    IngredientSchema,
    IngredientUpdateSchema,
)
from application.services.ingredient_service import IngredientService
from domain.models.ingredient import Ingredient


class IngredientRouter:
    def __init__(self, service: IngredientService, logger: Logger) -> None:
        self._service = service
        self._logger = logger
        self.router = APIRouter(
            prefix = "/v1/ingredients",
            tags = ["ingredients"],
            dependencies = [Depends(inject_tenant_uri)],
        )
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route(
            methods = ["POST"],
            path = "/",
            endpoint = self.create_ingredient,
            summary = "Create ingredient",
            response_model = ApiResponse[IngredientCreatedSchema],
            response_description = "UUID of the created ingredient",
            status_code = 201,
        )
        self.router.add_api_route(
            methods = ["GET"],
            path = "/",
            endpoint = self.list_ingredients,
            summary = "List ingredients",
            response_model = ApiResponse[list[IngredientSchema]],
            response_description = "List of active ingredients",
        )
        self.router.add_api_route(
            methods = ["DELETE"],
            path = "/purge",
            endpoint = self.purge_ingredients,
            summary = "Purge soft-deleted ingredients",
            response_model = ApiResponse[dict],
            response_description = "Number of permanently deleted records",
            status_code = 200,
        )
        self.router.add_api_route(
            methods = ["GET"],
            path = "/{uuid}",
            endpoint = self.get_ingredient,
            summary = "Get ingredient",
            response_model = ApiResponse[IngredientSchema],
            response_description = "The ingredient",
            responses = {404: {"description": "Ingredient not found"}},
        )
        self.router.add_api_route(
            methods = ["PUT"],
            path = "/{uuid}",
            endpoint = self.update_ingredient,
            summary = "Replace ingredient",
            status_code = 204,
            responses = {404: {"description": "Ingredient not found"}},
            response_model = None,
        )
        self.router.add_api_route(
            methods = ["PATCH"],
            path = "/{uuid}",
            endpoint = self.patch_ingredient,
            summary = "Partially update ingredient",
            status_code = 204,
            responses = {404: {"description": "Ingredient not found"}},
            response_model = None,
        )
        self.router.add_api_route(
            methods = ["DELETE"],
            path = "/{uuid}",
            endpoint = self.delete_ingredient,
            summary = "Delete ingredient",
            status_code = 204,
            response_model = None,
        )
        self.router.add_api_route(
            methods = ["POST"],
            path = "/{uuid}/duplicate",
            endpoint = self.duplicate_ingredient,
            summary = "Duplicate ingredient",
            response_model = ApiResponse[IngredientCreatedSchema],
            response_description = "UUID of the duplicated ingredient",
            status_code = 201,
        )

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    async def create_ingredient(self, payload: IngredientCreateSchema) -> ApiResponse[IngredientCreatedSchema]:
        """Create a new reusable ingredient."""
        result = await self._service.create(Ingredient(name = payload.name, unit = payload.unit))
        return success_response(
            data = IngredientCreatedSchema(uuid = result.uuid),
            links = {
                "self": f"/v1/ingredients/{result.uuid}",
                "collection": "/v1/ingredients",
            },
        )

    async def get_ingredient(self, uuid: StdUUID) -> ApiResponse[IngredientSchema]:
        """Get an ingredient by its UUID."""
        result = await self._service.read(self._to_uuid6(uuid))
        if result is None:
            self._logger.warning("⚠️ Ingredient not found via HTTP", uuid = str(uuid))
            raise HTTPException(status_code = 404, detail = "Ingredient not found")
        return success_response(
            data = IngredientSchema.model_validate(result, from_attributes = True),
            links = {
                "self": f"/v1/ingredients/{uuid}",
                "collection": "/v1/ingredients",
                "duplicate": f"/v1/ingredients/{uuid}/duplicate",
            },
        )

    async def update_ingredient(self, uuid: StdUUID, payload: IngredientUpdateSchema) -> None:
        """Replace name and unit of an existing ingredient (PUT semantics)."""
        await self._service.update(Ingredient(uuid = self._to_uuid6(uuid), name = payload.name, unit = payload.unit))

    async def patch_ingredient(self, uuid: StdUUID, payload: IngredientPatchSchema) -> None:
        """Partially update an ingredient (PATCH semantics)."""
        existing = await self._service.read(self._to_uuid6(uuid))
        if existing is None:
            self._logger.warning("⚠️ Ingredient not found via HTTP", uuid = str(uuid))
            raise HTTPException(status_code = 404, detail = "Ingredient not found")
        await self._service.update(
            Ingredient(
                uuid = existing.uuid,
                name = payload.name if payload.name is not None else existing.name,
                unit = payload.unit if payload.unit is not None else existing.unit,
            )
        )

    async def delete_ingredient(self, uuid: StdUUID) -> None:
        """Soft-delete an ingredient."""
        await self._service.delete(self._to_uuid6(uuid))

    async def list_ingredients(
            self,
            name: Annotated[
                str | None,
                Query(min_length = 1,
                      description = "Filtre optionnel : recherche partielle sur le nom (insensible à la casse).",
                      examples = ["farine"]),
            ] = None,
    ) -> ApiResponse[list[IngredientSchema]]:
        """List all active (non-deleted) ingredients."""
        items = await self._service.find_by_name(name) if name else await self._service.find_all()
        data = [IngredientSchema.model_validate(i, from_attributes = True) for i in items]
        return success_response(data = data, links = {"self": "/v1/ingredients"})

    async def duplicate_ingredient(self, uuid: StdUUID) -> ApiResponse[IngredientCreatedSchema]:
        """Duplicate an ingredient, assigning it a new UUID."""
        result = await self._service.duplicate(self._to_uuid6(uuid))
        return success_response(
            data = IngredientCreatedSchema(uuid = result.uuid),
            links = {
                "self": f"/v1/ingredients/{result.uuid}",
                "collection": "/v1/ingredients",
                "original": f"/v1/ingredients/{uuid}",
            },
        )

    async def purge_ingredients(self) -> ApiResponse[dict]:
        """Permanently delete soft-deleted ingredients that have exceeded the retention period."""
        purged = await self._service.purge()
        return success_response(data = {"purged": purged})
