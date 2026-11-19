from typing import Annotated
from uuid import UUID as StdUUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from uuid6 import UUID

from adapters.input.fastapi.dependencies import inject_tenant_uri, require_auth
from adapters.input.schemas.recipe_schema import RecipeSchema
from adapters.input.schemas.tag_schema import TagCreatedSchema, TagCreateSchema, TagPatchSchema, TagSchema, TagUpdateSchema
from application.services.recipe_service import RecipeService
from application.services.tag_service import TagService
from arclith.adapters.input.fastapi.dependencies import get_duration_ms
from arclith.adapters.input.schemas.response_wrapper import (
    ApiResponse,
    PaginatedResponse,
    ResponseMetadata,
    paginated_response,
    success_response,
)
from arclith.domain.ports.logger import Logger
from domain.models.tag import Tag


class TagRouter:
    def __init__(self, service: TagService, logger: Logger, recipe_service: RecipeService | None = None) -> None:
        self._service = service
        self._logger = logger
        self._recipe_service = recipe_service
        self.router = APIRouter(prefix="/v1/tags", tags=["tags"], dependencies=[Depends(inject_tenant_uri)])
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route(methods=["POST"], path="/", endpoint=self.create_tag, response_model=None, status_code=201)
        self.router.add_api_route(methods=["GET"], path="/", endpoint=self.list_tags, response_model=PaginatedResponse[TagSchema], status_code=200)
        self.router.add_api_route(methods=["GET"], path="/{uuid}", endpoint=self.get_tag, response_model=ApiResponse[TagSchema], status_code=200)
        self.router.add_api_route(methods=["PUT"], path="/{uuid}", endpoint=self.update_tag, status_code=204)
        self.router.add_api_route(methods=["PATCH"], path="/{uuid}", endpoint=self.patch_tag, status_code=204)
        self.router.add_api_route(
            methods=["DELETE"],
            path="/{uuid}",
            endpoint=self.delete_tag,
            status_code=204,
            responses={409: {"description": "Tag is used by at least one recipe"}},
            dependencies=[Depends(require_auth)],
        )
        self.router.add_api_route(methods=["GET"], path="/{uuid}/recipes", endpoint=self.list_recipes_for_tag, response_model=PaginatedResponse[RecipeSchema], status_code=200)

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    async def create_tag(
        self,
        payload: TagCreateSchema,
        response: Response,
        request: Request,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        prefer: Annotated[str | None, Header()] = None,
    ) -> ApiResponse[TagCreatedSchema] | ApiResponse[TagSchema]:
        result = await self._service.create(Tag(**payload.model_dump(exclude_none=True)))
        location = f"{request.url.path.rstrip('/')}/{result.uuid}"
        response.headers["Location"] = location
        if prefer and "return=representation" in prefer.lower():
            return success_response(TagSchema.model_validate(result), metadata=ResponseMetadata(duration_ms=int(duration_ms)))
        return success_response(TagCreatedSchema(uuid=result.uuid), metadata=ResponseMetadata(duration_ms=int(duration_ms)))

    async def get_tag(self, uuid: StdUUID, response: Response, duration_ms: Annotated[float, Depends(get_duration_ms)]) -> ApiResponse[TagSchema]:
        result = await self._service.read(self._to_uuid6(uuid))
        if result is None:
            raise HTTPException(status_code=404, detail="Tag not found")
        response.headers["ETag"] = f'"{result.version}"'
        return success_response(TagSchema.model_validate(result), metadata=ResponseMetadata(duration_ms=int(duration_ms)))

    async def update_tag(self, uuid: StdUUID, payload: TagUpdateSchema, response: Response) -> None:
        existing = await self._service.read(self._to_uuid6(uuid))
        if existing is None:
            raise HTTPException(status_code=404, detail="Tag not found")
        updated = await self._service.update(Tag(uuid=existing.uuid, version=existing.version, **payload.model_dump(exclude_none=True)))
        response.headers["ETag"] = f'"{updated.version}"'

    async def patch_tag(self, uuid: StdUUID, payload: TagPatchSchema, response: Response) -> None:
        existing = await self._service.read(self._to_uuid6(uuid))
        if existing is None:
            raise HTTPException(status_code=404, detail="Tag not found")
        data = existing.model_dump()
        for field_name, value in payload.model_dump(exclude_unset=True).items():
            data[field_name] = value
        updated = await self._service.update(Tag(**data))
        response.headers["ETag"] = f'"{updated.version}"'

    async def delete_tag(self, uuid: StdUUID) -> None:
        tag_uuid = self._to_uuid6(uuid)
        if self._recipe_service is not None and await self._recipe_service.is_tag_used(tag_uuid):
            raise HTTPException(status_code=409, detail="Tag is used by at least one recipe")
        await self._service.delete(tag_uuid)

    async def list_tags(
        self,
        response: Response,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=100),
        name: str | None = Query(None, min_length=1),
    ) -> PaginatedResponse[TagSchema]:
        offset = (page - 1) * per_page
        items, total = await self._service.find_page_filtered(name=name, offset=offset, limit=per_page)
        response.headers["X-Total-Count"] = str(total)
        return paginated_response(
            data=[TagSchema.model_validate(item) for item in items],
            total=total,
            page=page,
            per_page=per_page,
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def list_recipes_for_tag(
        self,
        uuid: StdUUID,
        response: Response,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=100),
    ) -> PaginatedResponse[RecipeSchema]:
        if await self._service.read(self._to_uuid6(uuid)) is None:
            raise HTTPException(status_code=404, detail="Tag not found")
        if self._recipe_service is None:
            raise HTTPException(status_code=503, detail="Recipe service is not available")
        offset = (page - 1) * per_page
        items, total = await self._recipe_service.find_page_filtered_hydrated(tag_uuid=self._to_uuid6(uuid), offset=offset, limit=per_page)
        response.headers["X-Total-Count"] = str(total)
        return paginated_response(
            data=[RecipeSchema.model_validate(item) for item in items],
            total=total,
            page=page,
            per_page=per_page,
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )
