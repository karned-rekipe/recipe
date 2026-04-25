from typing import Annotated
from uuid import UUID as StdUUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from uuid6 import UUID

from adapters.input.fastapi.dependencies import inject_tenant_uri, require_auth
from adapters.input.schemas.duplicate_schema import DuplicateGroupSchema, DuplicateMergeResultSchema, DuplicateMergeSchema
from adapters.input.schemas.ingredient_schema import (
    IngredientCreatedSchema,
    IngredientCreateSchema,
    IngredientPatchSchema,
    IngredientSchema,
    IngredientUpdateSchema,
)
from adapters.input.schemas.recipe_schema import RecipeSchema
from application.services.ingredient_service import IngredientDuplicateMergeError, IngredientReferenceError, IngredientService
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
from domain.models.ingredient import Ingredient


class IngredientRouter:
    def __init__(self, service: IngredientService, logger: Logger, recipe_service: RecipeService | None = None) -> None:
        self._service = service
        self._logger = logger
        self._recipe_service = recipe_service
        self.router = APIRouter(prefix="/v1/ingredients", tags=["ingredients"], dependencies=[Depends(inject_tenant_uri)])
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route(
            methods=["POST"],
            path="/",
            endpoint=self.create_ingredient,
            summary="Create ingredient",
            response_model=ApiResponse[IngredientCreatedSchema],
            status_code=201,
            responses={
                400: {"description": "Invalid payload"},
                422: {"description": "Validation failed"},
            },
        )
        self.router.add_api_route(
            methods=["GET"],
            path="/",
            endpoint=self.list_ingredients,
            summary="List ingredients",
            response_model=PaginatedResponse[IngredientSchema],
            status_code=200,
        )
        self.router.add_api_route(
            methods=["GET"],
            path="/duplicates",
            endpoint=self.list_duplicates,
            summary="List ingredient duplicate groups",
            response_model=ApiResponse[list[DuplicateGroupSchema]],
            status_code=200,
        )
        self.router.add_api_route(
            methods=["POST"],
            path="/duplicates/merge",
            endpoint=self.merge_duplicates,
            summary="Merge ingredient duplicates",
            response_model=ApiResponse[DuplicateMergeResultSchema],
            status_code=200,
            responses={409: {"description": "Merge conflict"}},
            dependencies=[Depends(require_auth)],
        )
        self.router.add_api_route(
            methods=["GET"],
            path="/{uuid}",
            endpoint=self.get_ingredient,
            summary="Get ingredient",
            response_model=ApiResponse[IngredientSchema],
            status_code=200,
            responses={
                404: {"description": "Ingredient not found"},
            },
        )
        self.router.add_api_route(
            methods=["PUT"],
            path="/{uuid}",
            endpoint=self.update_ingredient,
            summary="Replace ingredient",
            status_code=204,
            responses={
                404: {"description": "Ingredient not found"},
                412: {"description": "Precondition Failed (version mismatch via If-Match)"},
                422: {"description": "Validation failed"},
            },
        )
        self.router.add_api_route(
            methods=["PATCH"],
            path="/{uuid}",
            endpoint=self.patch_ingredient,
            summary="Partially update ingredient",
            status_code=204,
            responses={
                404: {"description": "Ingredient not found"},
                412: {"description": "Precondition Failed (version mismatch via If-Match)"},
                422: {"description": "Validation failed"},
            },
        )
        self.router.add_api_route(
            methods=["DELETE"],
            path="/{uuid}",
            endpoint=self.delete_ingredient,
            summary="Delete ingredient",
            status_code=204,
            responses={
                404: {"description": "Ingredient not found"},
                409: {"description": "Ingredient is used by at least one recipe"},
            },
            dependencies=[Depends(require_auth)],
        )
        self.router.add_api_route(
            methods=["GET"],
            path="/{uuid}/recipes",
            endpoint=self.list_recipes_for_ingredient,
            summary="List recipes using ingredient",
            response_model=PaginatedResponse[RecipeSchema],
            status_code=200,
            responses={
                404: {"description": "Ingredient not found"},
            },
        )
        self.router.add_api_route(
            methods=["POST"],
            path="/{uuid}/duplicate",
            endpoint=self.duplicate_ingredient,
            summary="Duplicate ingredient",
            response_model=ApiResponse[IngredientCreatedSchema],
            status_code=201,
            responses={
                404: {"description": "Ingredient not found"},
            },
        )

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    async def create_ingredient(
        self,
        payload: IngredientCreateSchema,
        response: Response,
        request: Request,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        prefer: Annotated[str | None, Header()] = None,
    ) -> ApiResponse[IngredientCreatedSchema] | ApiResponse[IngredientSchema]:
        """Create a new ingredient."""
        try:
            result = await self._service.create(Ingredient(
                name=payload.name,
                rayon_uuid=self._to_uuid6(payload.rayon_uuid) if payload.rayon_uuid is not None else None,
                group_uuid=self._to_uuid6(payload.group_uuid) if payload.group_uuid is not None else None,
                green_score=payload.green_score,
                unit=payload.unit,
                quantity=payload.quantity,
                season_months=payload.season_months,
            ))
        except IngredientReferenceError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        location = f"{request.url.path.rstrip('/')}/{result.uuid}"
        response.headers["Location"] = location
        response.headers["Link"] = f'<{location}>; rel="self", <{location}/duplicate>; rel="duplicate"'

        if prefer and "return=representation" in prefer.lower():
            return success_response(
                IngredientSchema.model_validate(await self._service.hydrate_ingredient(result)),
                metadata=ResponseMetadata(duration_ms=int(duration_ms)),
            )

        return success_response(
            IngredientCreatedSchema(uuid=result.uuid),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def get_ingredient(
        self,
        uuid: StdUUID,
        response: Response,
        request: Request,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
    ) -> ApiResponse[IngredientSchema]:
        """Get an ingredient by its UUID."""
        result = await self._service.read(self._to_uuid6(uuid))
        if result is None:
            self._logger.warning("⚠️ Ingredient not found via HTTP", uuid=str(uuid))
            raise HTTPException(status_code=404, detail="Ingredient not found")

        response.headers["ETag"] = f'"{result.version}"'
        base = f"{request.url.path.rstrip('/')}"
        response.headers["Link"] = f'<{base}>; rel="self", <{base}/duplicate>; rel="duplicate", </v1/ingredients>; rel="collection"'

        return success_response(
            IngredientSchema.model_validate(await self._service.hydrate_ingredient(result)),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def update_ingredient(
        self,
        uuid: StdUUID,
        payload: IngredientUpdateSchema,
        response: Response,
        request: Request,
        if_match: Annotated[str | None, Header()] = None,
    ) -> None:
        """Replace an existing ingredient (PUT semantics)."""
        existing = await self._service.read(self._to_uuid6(uuid))
        if existing is None:
            self._logger.warning("⚠️ Ingredient not found via HTTP (PUT)", uuid=str(uuid))
            raise HTTPException(status_code=404, detail="Ingredient not found")

        if if_match:
            expected_version = int(if_match.strip('"').lstrip('vV'))
            if existing.version != expected_version:
                self._logger.warning(
                    "⚠️ Version mismatch (optimistic lock failure)",
                    uuid=str(uuid),
                    expected=expected_version,
                    current=existing.version,
                )
                raise HTTPException(
                    status_code=412,
                    detail=f"Version mismatch: expected v{expected_version}, current v{existing.version}",
                )

        try:
            updated = await self._service.update(Ingredient(
                uuid=self._to_uuid6(uuid),
                name=payload.name,
                rayon_uuid=self._to_uuid6(payload.rayon_uuid) if payload.rayon_uuid is not None else None,
                group_uuid=self._to_uuid6(payload.group_uuid) if payload.group_uuid is not None else None,
                green_score=payload.green_score,
                unit=payload.unit,
                quantity=payload.quantity,
                season_months=payload.season_months,
            ))
        except IngredientReferenceError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        response.headers["Content-Location"] = f"/v1/ingredients/{uuid}"
        response.headers["ETag"] = f'"{updated.version}"'

    async def patch_ingredient(
        self,
        uuid: StdUUID,
        payload: IngredientPatchSchema,
        response: Response,
        request: Request,
        if_match: Annotated[str | None, Header()] = None,
    ) -> None:
        """Partially update an ingredient (PATCH semantics)."""
        existing = await self._service.read(self._to_uuid6(uuid))
        if existing is None:
            self._logger.warning("⚠️ Ingredient not found via HTTP (PATCH)", uuid=str(uuid))
            raise HTTPException(status_code=404, detail="Ingredient not found")

        if if_match:
            expected_version = int(if_match.strip('"').lstrip('vV'))
            if existing.version != expected_version:
                self._logger.warning(
                    "⚠️ Version mismatch (optimistic lock failure)",
                    uuid=str(uuid),
                    expected=expected_version,
                    current=existing.version,
                )
                raise HTTPException(
                    status_code=412,
                    detail=f"Version mismatch: expected v{expected_version}, current v{existing.version}",
                )

        fields_set = payload.model_fields_set
        try:
            updated = await self._service.update(Ingredient(
                uuid=existing.uuid,
                name=payload.name if "name" in fields_set and payload.name is not None else existing.name,
                rayon_uuid=self._to_uuid6(payload.rayon_uuid)
                if "rayon_uuid" in fields_set and payload.rayon_uuid is not None
                else None if "rayon_uuid" in fields_set else existing.rayon_uuid,
                group_uuid=self._to_uuid6(payload.group_uuid)
                if "group_uuid" in fields_set and payload.group_uuid is not None
                else None if "group_uuid" in fields_set else existing.group_uuid,
                green_score=payload.green_score if "green_score" in fields_set else existing.green_score,
                unit=payload.unit if "unit" in fields_set else existing.unit,
                quantity=payload.quantity if "quantity" in fields_set else existing.quantity,
                season_months=payload.season_months if payload.season_months is not None else existing.season_months,
            ))
        except IngredientReferenceError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        response.headers["Content-Location"] = f"/v1/ingredients/{uuid}"
        response.headers["ETag"] = f'"{updated.version}"'

    async def delete_ingredient(self, uuid: StdUUID) -> None:
        """Soft-delete an ingredient."""
        if self._recipe_service is not None and await self._recipe_service.is_ingredient_used(self._to_uuid6(uuid)):
            raise HTTPException(status_code=409, detail="Ingredient is used by at least one recipe")
        await self._service.delete(self._to_uuid6(uuid))

    async def list_recipes_for_ingredient(
        self,
        uuid: StdUUID,
        response: Response,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    ) -> PaginatedResponse[RecipeSchema]:
        """List recipes referencing an ingredient."""
        ingredient = await self._service.read(self._to_uuid6(uuid))
        if ingredient is None:
            raise HTTPException(status_code=404, detail="Ingredient not found")
        if self._recipe_service is None:
            raise HTTPException(status_code=503, detail="Recipe service is not available")

        offset = (page - 1) * per_page
        items, total = await self._recipe_service.find_page_filtered_hydrated(
            ingredient_uuid=self._to_uuid6(uuid),
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

    async def list_ingredients(
        self,
        response: Response,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        per_page: int = Query(20, ge=1, le=100, description="Items per page"),
        name: str | None = Query(None, min_length=1, description="Filter by name (partial, case-insensitive)"),
        group_uuid: StdUUID | None = Query(None, description="Filter by ingredient group UUID"),
        rayon_uuid: StdUUID | None = Query(None, description="Filter by ingredient rayon UUID"),
    ) -> PaginatedResponse[IngredientSchema]:
        """List all active (non-deleted) ingredients."""
        offset = (page - 1) * per_page
        items, total = await self._service.find_page_filtered(
            name=name,
            group_uuid=self._to_uuid6(group_uuid) if group_uuid is not None else None,
            rayon_uuid=self._to_uuid6(rayon_uuid) if rayon_uuid is not None else None,
            offset=offset,
            limit=per_page,
        )

        response.headers["X-Total-Count"] = str(total)

        return paginated_response(
            data=[IngredientSchema.model_validate(item) for item in await self._service.hydrate_ingredients(items)],
            total=total,
            page=page,
            per_page=per_page,
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def list_duplicates(
        self,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
    ) -> ApiResponse[list[DuplicateGroupSchema]]:
        """List duplicate ingredient groups detected by normalized name."""
        return success_response(
            [DuplicateGroupSchema.model_validate(group) for group in await self._service.find_duplicate_groups()],
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def merge_duplicates(
        self,
        payload: DuplicateMergeSchema,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
    ) -> ApiResponse[DuplicateMergeResultSchema]:
        """Merge duplicate ingredients into an explicit canonical target."""
        if self._recipe_service is None:
            raise HTTPException(status_code=503, detail="Recipe service is not available")
        try:
            result = await self._service.merge_duplicates(
                self._to_uuid6(payload.target_uuid),
                [self._to_uuid6(uuid) for uuid in payload.duplicate_uuids],
                self._recipe_service,
            )
        except (IngredientDuplicateMergeError, RecipeMergeConflict) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        return success_response(
            DuplicateMergeResultSchema.model_validate(result),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def duplicate_ingredient(
        self,
        uuid: StdUUID,
        response: Response,
        request: Request,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        prefer: Annotated[str | None, Header()] = None,
    ) -> ApiResponse[IngredientCreatedSchema] | ApiResponse[IngredientSchema]:
        """Duplicate an ingredient, assigning it a new UUID."""
        result = await self._service.duplicate(self._to_uuid6(uuid))

        location = f"/v1/ingredients/{result.uuid}"
        response.headers["Location"] = location
        response.headers["Link"] = f'<{location}>; rel="self", </v1/ingredients>; rel="collection"'

        if prefer and "return=representation" in prefer.lower():
            return success_response(
                IngredientSchema.model_validate(await self._service.hydrate_ingredient(result)),
                metadata=ResponseMetadata(duration_ms=int(duration_ms)),
            )

        return success_response(
            IngredientCreatedSchema(uuid=result.uuid),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )
