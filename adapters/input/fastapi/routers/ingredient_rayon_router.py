from typing import Annotated
from uuid import UUID as StdUUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from uuid6 import UUID

from adapters.input.fastapi.dependencies import inject_tenant_uri, require_auth
from adapters.input.schemas.ingredient_rayon_schema import (
    IngredientRayonCreatedSchema,
    IngredientRayonCreateSchema,
    IngredientRayonPatchSchema,
    IngredientRayonSchema,
    IngredientRayonUpdateSchema,
)
from application.services.ingredient_rayon_service import IngredientRayonService
from application.services.ingredient_service import IngredientService
from arclith.adapters.input.fastapi.dependencies import get_duration_ms
from arclith.adapters.input.schemas.response_wrapper import ApiResponse, PaginatedResponse, ResponseMetadata, paginated_response, success_response
from arclith.domain.ports.logger import Logger
from domain.models.ingredient_rayon import IngredientRayon


class IngredientRayonRouter:
    def __init__(self, service: IngredientRayonService, logger: Logger, ingredient_service: IngredientService | None = None) -> None:
        self._service = service
        self._logger = logger
        self._ingredient_service = ingredient_service
        self.router = APIRouter(prefix="/v1/ingredient-rayons", tags=["ingredient-rayons"], dependencies=[Depends(inject_tenant_uri)])
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route(methods=["POST"], path="/", endpoint=self.create_rayon, response_model=ApiResponse[IngredientRayonCreatedSchema], status_code=201)
        self.router.add_api_route(methods=["GET"], path="/", endpoint=self.list_rayons, response_model=PaginatedResponse[IngredientRayonSchema], status_code=200)
        self.router.add_api_route(methods=["GET"], path="/{uuid}", endpoint=self.get_rayon, response_model=ApiResponse[IngredientRayonSchema], status_code=200)
        self.router.add_api_route(methods=["PUT"], path="/{uuid}", endpoint=self.update_rayon, status_code=204)
        self.router.add_api_route(methods=["PATCH"], path="/{uuid}", endpoint=self.patch_rayon, status_code=204)
        self.router.add_api_route(
            methods=["DELETE"],
            path="/{uuid}",
            endpoint=self.delete_rayon,
            status_code=204,
            responses={409: {"description": "Ingredient rayon is used by at least one ingredient"}},
            dependencies=[Depends(require_auth)],
        )

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    async def create_rayon(
        self,
        payload: IngredientRayonCreateSchema,
        response: Response,
        request: Request,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        prefer: Annotated[str | None, Header()] = None,
    ) -> ApiResponse[IngredientRayonCreatedSchema] | ApiResponse[IngredientRayonSchema]:
        result = await self._service.create(IngredientRayon(**payload.model_dump(exclude_none=True)))
        location = f"{request.url.path.rstrip('/')}/{result.uuid}"
        response.headers["Location"] = location
        if prefer and "return=representation" in prefer.lower():
            return success_response(IngredientRayonSchema.model_validate(result), metadata=ResponseMetadata(duration_ms=int(duration_ms)))
        return success_response(IngredientRayonCreatedSchema(uuid=result.uuid), metadata=ResponseMetadata(duration_ms=int(duration_ms)))

    async def get_rayon(self, uuid: StdUUID, response: Response, duration_ms: Annotated[float, Depends(get_duration_ms)]) -> ApiResponse[IngredientRayonSchema]:
        result = await self._service.read(self._to_uuid6(uuid))
        if result is None:
            raise HTTPException(status_code=404, detail="Ingredient rayon not found")
        response.headers["ETag"] = f'"{result.version}"'
        return success_response(IngredientRayonSchema.model_validate(result), metadata=ResponseMetadata(duration_ms=int(duration_ms)))

    async def update_rayon(self, uuid: StdUUID, payload: IngredientRayonUpdateSchema, response: Response) -> None:
        existing = await self._service.read(self._to_uuid6(uuid))
        if existing is None:
            raise HTTPException(status_code=404, detail="Ingredient rayon not found")
        updated = await self._service.update(IngredientRayon(uuid=existing.uuid, version=existing.version, **payload.model_dump(exclude_none=True)))
        response.headers["ETag"] = f'"{updated.version}"'

    async def patch_rayon(self, uuid: StdUUID, payload: IngredientRayonPatchSchema, response: Response) -> None:
        existing = await self._service.read(self._to_uuid6(uuid))
        if existing is None:
            raise HTTPException(status_code=404, detail="Ingredient rayon not found")
        data = existing.model_dump()
        for field_name, value in payload.model_dump(exclude_unset=True).items():
            data[field_name] = value
        updated = await self._service.update(IngredientRayon(**data))
        response.headers["ETag"] = f'"{updated.version}"'

    async def delete_rayon(self, uuid: StdUUID) -> None:
        rayon_uuid = self._to_uuid6(uuid)
        if self._ingredient_service is not None and await self._ingredient_service.is_rayon_used(rayon_uuid):
            raise HTTPException(status_code=409, detail="Ingredient rayon is used by at least one ingredient")
        await self._service.delete(rayon_uuid)

    async def list_rayons(
        self,
        response: Response,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        page: int = Query(1, ge=1),
        per_page: int = Query(100, ge=1, le=100),
        name: str | None = Query(None, min_length=1),
    ) -> PaginatedResponse[IngredientRayonSchema]:
        offset = (page - 1) * per_page
        items, total = await self._service.find_page_filtered(name=name, offset=offset, limit=per_page)
        response.headers["X-Total-Count"] = str(total)
        return paginated_response(
            data=[IngredientRayonSchema.model_validate(item) for item in items],
            total=total,
            page=page,
            per_page=per_page,
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )
