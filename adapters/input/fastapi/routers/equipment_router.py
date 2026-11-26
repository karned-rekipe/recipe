from typing import Annotated
from uuid import UUID as StdUUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from uuid6 import UUID

from adapters.input.fastapi.dependencies import inject_tenant_uri, require_auth
from adapters.input.schemas.duplicate_schema import DuplicateGroupSchema, DuplicateMergeResultSchema, DuplicateMergeSchema
from adapters.input.schemas.equipment_schema import (
    EquipmentCreatedSchema,
    EquipmentCreateSchema,
    EquipmentImageGenerationRequestSchema,
    EquipmentImageGenerationResponseSchema,
    EquipmentPatchSchema,
    EquipmentSchema,
    EquipmentUpdateSchema,
)
from adapters.input.schemas.recipe_schema import RecipeSchema
from application.services.equipment_service import (
    EquipmentDuplicateMergeError,
    EquipmentImageAlreadyExistsError,
    EquipmentImageGenerationConflictError,
    EquipmentImageGenerationInProgressError,
    EquipmentImageGenerationUnavailableError,
    EquipmentService,
)
from application.services.recipe_service import RecipeMergeConflict, RecipeService
from arclith.adapters.input.fastapi.dependencies import get_duration_ms
from arclith.adapters.input.schemas.response_wrapper import (
    ApiResponse,
    PaginatedResponse,
    ResponseMetadata,
    paginated_response,
    success_response,
)
from arclith.domain.ports.logger import Logger
from domain.models.equipment import Equipment
from domain.ports.output.image_generator import ImageGenerationRateLimitError


class EquipmentRouter:
    def __init__(self, service: EquipmentService, logger: Logger, recipe_service: RecipeService | None = None) -> None:
        self._service = service
        self._logger = logger
        self._recipe_service = recipe_service
        self.router = APIRouter(prefix="/v1/equipment", tags=["equipment"], dependencies=[Depends(inject_tenant_uri)])
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route(
            methods=["POST"],
            path="/",
            endpoint=self.create_equipment,
            summary="Create equipment",
            response_model=ApiResponse[EquipmentCreatedSchema],
            status_code=201,
            responses={400: {"description": "Invalid payload"}, 422: {"description": "Validation failed"}},
        )
        self.router.add_api_route(
            methods=["GET"],
            path="/",
            endpoint=self.list_equipment,
            summary="List equipment",
            response_model=PaginatedResponse[EquipmentSchema],
            status_code=200,
        )
        self.router.add_api_route(
            methods=["GET"],
            path="/duplicates",
            endpoint=self.list_duplicates,
            summary="List equipment duplicate groups",
            response_model=ApiResponse[list[DuplicateGroupSchema]],
            status_code=200,
        )
        self.router.add_api_route(
            methods=["POST"],
            path="/duplicates/merge",
            endpoint=self.merge_duplicates,
            summary="Merge equipment duplicates",
            response_model=ApiResponse[DuplicateMergeResultSchema],
            status_code=200,
            responses={409: {"description": "Merge conflict"}},
            dependencies=[Depends(require_auth)],
        )
        self.router.add_api_route(
            methods=["GET"],
            path="/{uuid}",
            endpoint=self.get_equipment,
            summary="Get equipment",
            response_model=ApiResponse[EquipmentSchema],
            status_code=200,
            responses={404: {"description": "Equipment not found"}},
        )
        self.router.add_api_route(
            methods=["POST"],
            path="/{uuid}/main-image",
            endpoint=self.generate_equipment_image,
            summary="Generate and attach the equipment main image",
            response_model=ApiResponse[EquipmentImageGenerationResponseSchema],
            status_code=200,
            responses={
                404: {"description": "Equipment not found"},
                409: {"description": "Equipment already has a main image"},
                429: {"description": "Image generation quota or rate limit reached"},
                502: {"description": "Media image generation failed"},
                503: {"description": "Image generation is not configured"},
            },
            dependencies=[Depends(require_auth)],
        )
        self.router.add_api_route(
            methods=["PUT"],
            path="/{uuid}",
            endpoint=self.update_equipment,
            summary="Replace equipment",
            status_code=204,
            responses={
                404: {"description": "Equipment not found"},
                412: {"description": "Precondition Failed (version mismatch via If-Match)"},
                422: {"description": "Validation failed"},
            },
        )
        self.router.add_api_route(
            methods=["PATCH"],
            path="/{uuid}",
            endpoint=self.patch_equipment,
            summary="Partially update equipment",
            status_code=204,
            responses={
                404: {"description": "Equipment not found"},
                412: {"description": "Precondition Failed (version mismatch via If-Match)"},
                422: {"description": "Validation failed"},
            },
        )
        self.router.add_api_route(
            methods=["DELETE"],
            path="/{uuid}",
            endpoint=self.delete_equipment,
            summary="Delete equipment",
            status_code=204,
            responses={
                404: {"description": "Equipment not found"},
                409: {"description": "Equipment is used by at least one recipe"},
            },
            dependencies=[Depends(require_auth)],
        )
        self.router.add_api_route(
            methods=["POST"],
            path="/{uuid}/duplicate",
            endpoint=self.duplicate_equipment,
            summary="Duplicate equipment",
            response_model=ApiResponse[EquipmentCreatedSchema],
            status_code=201,
            responses={404: {"description": "Equipment not found"}},
        )
        self.router.add_api_route(
            methods=["GET"],
            path="/{uuid}/recipes",
            endpoint=self.list_recipes_for_equipment,
            summary="List recipes using equipment",
            response_model=PaginatedResponse[RecipeSchema],
            status_code=200,
            responses={404: {"description": "Equipment not found"}},
        )

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    async def create_equipment(
        self,
        payload: EquipmentCreateSchema,
        response: Response,
        request: Request,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        prefer: Annotated[str | None, Header()] = None,
    ) -> ApiResponse[EquipmentCreatedSchema] | ApiResponse[EquipmentSchema]:
        """Create a new equipment item."""
        result = await self._service.create(Equipment(name=payload.name, description=payload.description))

        location = f"{request.url.path.rstrip('/')}/{result.uuid}"
        response.headers["Location"] = location
        response.headers["Link"] = f'<{location}>; rel="self", <{location}/duplicate>; rel="duplicate"'

        if prefer and "return=representation" in prefer.lower():
            return success_response(
                EquipmentSchema.model_validate(result, from_attributes=True),
                metadata=ResponseMetadata(duration_ms=int(duration_ms)),
            )

        return success_response(
            EquipmentCreatedSchema(uuid=result.uuid),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def get_equipment(
        self,
        uuid: StdUUID,
        response: Response,
        request: Request,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
    ) -> ApiResponse[EquipmentSchema]:
        """Get equipment by UUID."""
        result = await self._service.read(self._to_uuid6(uuid))
        if result is None:
            self._logger.warning("⚠️ Equipment not found via HTTP", uuid=str(uuid))
            raise HTTPException(status_code=404, detail="Equipment not found")

        response.headers["ETag"] = f'"{result.version}"'
        base = f"{request.url.path.rstrip('/')}"
        response.headers["Link"] = f'<{base}>; rel="self", <{base}/duplicate>; rel="duplicate", </v1/equipment>; rel="collection"'
        return success_response(
            EquipmentSchema.model_validate(result, from_attributes=True),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def generate_equipment_image(
        self,
        uuid: StdUUID,
        payload: EquipmentImageGenerationRequestSchema,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
    ) -> ApiResponse[EquipmentImageGenerationResponseSchema]:
        """Generate, store, and attach an equipment main image through media."""
        try:
            equipment, generated = await self._service.generate_main_image(
                self._to_uuid6(uuid),
                replace_existing=payload.replace_existing,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Equipment not found") from exc
        except (
            EquipmentImageAlreadyExistsError,
            EquipmentImageGenerationConflictError,
            EquipmentImageGenerationInProgressError,
        ) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except EquipmentImageGenerationUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ImageGenerationRateLimitError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        self._logger.info(
            "✅ Equipment image generated via HTTP",
            uuid=str(uuid),
            provider=generated.provider,
            image_url=generated.image.url,
        )
        return success_response(
            EquipmentImageGenerationResponseSchema(
                equipment=EquipmentSchema.model_validate(equipment, from_attributes=True),
                **generated.model_dump(),
            ),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def update_equipment(
        self,
        uuid: StdUUID,
        payload: EquipmentUpdateSchema,
        response: Response,
        request: Request,
        if_match: Annotated[str | None, Header()] = None,
    ) -> None:
        """Replace equipment."""
        existing = await self._service.read(self._to_uuid6(uuid))
        if existing is None:
            raise HTTPException(status_code=404, detail="Equipment not found")
        self._raise_if_version_mismatch(existing, uuid, if_match)

        updated = await self._service.update(Equipment(
            uuid=self._to_uuid6(uuid),
            name=payload.name,
            description=payload.description,
            main_image=existing.main_image,
        ))
        response.headers["Content-Location"] = f"/v1/equipment/{uuid}"
        response.headers["ETag"] = f'"{updated.version}"'

    async def patch_equipment(
        self,
        uuid: StdUUID,
        payload: EquipmentPatchSchema,
        response: Response,
        request: Request,
        if_match: Annotated[str | None, Header()] = None,
    ) -> None:
        """Partially update equipment."""
        existing = await self._service.read(self._to_uuid6(uuid))
        if existing is None:
            raise HTTPException(status_code=404, detail="Equipment not found")
        self._raise_if_version_mismatch(existing, uuid, if_match)

        updated = await self._service.update(Equipment(
            uuid=existing.uuid,
            name=payload.name if payload.name is not None else existing.name,
            description=payload.description if payload.description is not None else existing.description,
            main_image=existing.main_image,
        ))
        response.headers["Content-Location"] = f"/v1/equipment/{uuid}"
        response.headers["ETag"] = f'"{updated.version}"'

    async def delete_equipment(self, uuid: StdUUID) -> None:
        """Soft-delete equipment if it is not used by a recipe."""
        if self._recipe_service is not None and await self._recipe_service.is_equipment_used(self._to_uuid6(uuid)):
            raise HTTPException(status_code=409, detail="Equipment is used by at least one recipe")
        await self._service.delete(self._to_uuid6(uuid))

    async def list_equipment(
        self,
        response: Response,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        per_page: int = Query(20, ge=1, le=100, description="Items per page"),
        name: str | None = Query(None, min_length=1, description="Filter by name (partial, case-insensitive)"),
    ) -> PaginatedResponse[EquipmentSchema]:
        """List active equipment."""
        offset = (page - 1) * per_page
        items, total = await self._service.find_page_filtered(name=name, offset=offset, limit=per_page)
        response.headers["X-Total-Count"] = str(total)
        return paginated_response(
            data=[EquipmentSchema.model_validate(item, from_attributes=True) for item in items],
            total=total,
            page=page,
            per_page=per_page,
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def list_duplicates(
        self,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
    ) -> ApiResponse[list[DuplicateGroupSchema]]:
        """List duplicate equipment groups detected by normalized name."""
        return success_response(
            [DuplicateGroupSchema.model_validate(group) for group in await self._service.find_duplicate_groups()],
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def merge_duplicates(
        self,
        payload: DuplicateMergeSchema,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
    ) -> ApiResponse[DuplicateMergeResultSchema]:
        """Merge duplicate equipment into an explicit canonical target."""
        if self._recipe_service is None:
            raise HTTPException(status_code=503, detail="Recipe service is not available")
        try:
            result = await self._service.merge_duplicates(
                self._to_uuid6(payload.target_uuid),
                [self._to_uuid6(uuid) for uuid in payload.duplicate_uuids],
                self._recipe_service,
            )
        except (EquipmentDuplicateMergeError, RecipeMergeConflict) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        return success_response(
            DuplicateMergeResultSchema.model_validate(result),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def duplicate_equipment(
        self,
        uuid: StdUUID,
        response: Response,
        request: Request,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        prefer: Annotated[str | None, Header()] = None,
    ) -> ApiResponse[EquipmentCreatedSchema] | ApiResponse[EquipmentSchema]:
        """Duplicate equipment."""
        result = await self._service.duplicate(self._to_uuid6(uuid))
        location = f"/v1/equipment/{result.uuid}"
        response.headers["Location"] = location
        response.headers["Link"] = f'<{location}>; rel="self", </v1/equipment>; rel="collection"'

        if prefer and "return=representation" in prefer.lower():
            return success_response(
                EquipmentSchema.model_validate(result, from_attributes=True),
                metadata=ResponseMetadata(duration_ms=int(duration_ms)),
            )

        return success_response(
            EquipmentCreatedSchema(uuid=result.uuid),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def list_recipes_for_equipment(
        self,
        uuid: StdUUID,
        response: Response,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    ) -> PaginatedResponse[RecipeSchema]:
        """List recipes referencing equipment."""
        equipment = await self._service.read(self._to_uuid6(uuid))
        if equipment is None:
            raise HTTPException(status_code=404, detail="Equipment not found")
        if self._recipe_service is None:
            raise HTTPException(status_code=503, detail="Recipe service is not available")

        offset = (page - 1) * per_page
        items, total = await self._recipe_service.find_page_filtered_hydrated(
            equipment_uuid=self._to_uuid6(uuid),
            offset=offset,
            limit=per_page,
        )
        response.headers["X-Total-Count"] = str(total)
        return paginated_response(
            data=[RecipeSchema.model_validate(item) for item in items],
            total=total,
            page=page,
            per_page=per_page,
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    def _raise_if_version_mismatch(self, existing: Equipment, uuid: StdUUID, if_match: str | None) -> None:
        if not if_match:
            return
        expected_version = int(if_match.strip('"').lstrip("vV"))
        if existing.version == expected_version:
            return
        self._logger.warning(
            "⚠️ Equipment version mismatch",
            uuid=str(uuid),
            expected=expected_version,
            current=existing.version,
        )
        raise HTTPException(
            status_code=412,
            detail=f"Version mismatch: expected v{expected_version}, current v{existing.version}",
        )
