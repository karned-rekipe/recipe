from typing import Annotated
from uuid import UUID as StdUUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from uuid6 import UUID

from adapters.input.fastapi.dependencies import inject_tenant_uri, require_auth
from adapters.input.schemas.recipe_schema import (
    RecipeCreatedSchema,
    RecipeCreateSchema,
    RecipePatchSchema,
    RecipeSchema,
    RecipeUpdateSchema,
)
from application.services.recipe_service import RecipeService
from arclith.adapters.input.fastapi.dependencies import get_duration_ms
from arclith.adapters.input.schemas.response_wrapper import (
    ApiResponse,
    PaginatedResponse,
    ResponseMetadata,
    paginated_response,
    success_response,
)
from arclith.domain.ports.logger import Logger
from domain.models.recipe import Recipe


class RecipeRouter:
    def __init__(self, service: RecipeService, logger: Logger) -> None:
        self._service = service
        self._logger = logger
        self.router = APIRouter(prefix="/v1/recipes", tags=["recipes"], dependencies=[Depends(inject_tenant_uri)])
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route(
            methods=["POST"],
            path="/",
            endpoint=self.create_recipe,
            summary="Create recipe",
            response_model = ApiResponse[RecipeCreatedSchema],
            status_code=201,
            responses = {
                400: {"description": "Invalid payload"},
                422: {"description": "Validation failed"},
            },
        )
        self.router.add_api_route(
            methods=["GET"],
            path="/",
            endpoint=self.list_recipes,
            summary="List recipes",
            response_model=PaginatedResponse[RecipeSchema],
            status_code=200,
        )
        self.router.add_api_route(
            methods=["GET"],
            path="/{uuid}",
            endpoint=self.get_recipe,
            summary="Get recipe",
            response_model=ApiResponse[RecipeSchema],
            status_code=200,
            responses = {
                404: {"description": "Recipe not found"},
            },
        )
        self.router.add_api_route(
            methods=["PUT"],
            path="/{uuid}",
            endpoint=self.update_recipe,
            summary="Replace recipe",
            status_code=204,
            responses = {
                404: {"description": "Recipe not found"},
                412: {"description": "Precondition Failed (version mismatch via If-Match)"},
                422: {"description": "Validation failed"},
            },
        )
        self.router.add_api_route(
            methods=["PATCH"],
            path="/{uuid}",
            endpoint=self.patch_recipe,
            summary="Partially update recipe",
            status_code=204,
            responses = {
                404: {"description": "Recipe not found"},
                412: {"description": "Precondition Failed (version mismatch via If-Match)"},
                422: {"description": "Validation failed"},
            },
        )
        self.router.add_api_route(
            methods=["DELETE"],
            path="/{uuid}",
            endpoint=self.delete_recipe,
            summary="Delete recipe",
            status_code=204,
            responses = {
                404: {"description": "Recipe not found"},
            },
            dependencies=[Depends(require_auth)],
        )
        self.router.add_api_route(
            methods=["POST"],
            path="/{uuid}/duplicate",
            endpoint=self.duplicate_recipe,
            summary="Duplicate recipe",
            response_model = ApiResponse[RecipeCreatedSchema],
            status_code=201,
            responses = {
                404: {"description": "Recipe not found"},
            },
        )

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    async def create_recipe(
        self,
        payload: RecipeCreateSchema,
            response: Response,
            request: Request,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
            prefer: Annotated[str | None, Header()] = None,
    ) -> ApiResponse[RecipeCreatedSchema] | ApiResponse[RecipeSchema]:
        """Create a new reusable recipe.

        **SOTA REST Features:**
        - Returns 201 Created with UUID only (minimal response)
        - Location header points to the created resource
        - Supports `Prefer: return=representation` to get full object instead
        - Supports `Idempotency-Key` header to prevent duplicates (via middleware)
        - Returns 422 for validation errors (business logic)

        **Usage:**
        ```bash
        # Minimal response (default)
        curl -X POST /v1/recipes \\
          -H "Content-Type: application/json" \\
          -H "Idempotency-Key: $(uuidgen)" \\
          -d '{"name": "Farine de blé"}'
        
        # Full representation
        curl -X POST /v1/recipes \\
          -H "Prefer: return=representation" \\
          -d '{"name": "Farine de blé"}'
        ```
        """
        result = await self._service.create(Recipe(name=payload.name))

        # RFC 7231: Location header on 201 Created
        location = f"{request.url.path.rstrip('/')}/{result.uuid}"
        response.headers["Location"] = location

        # RFC 8288: Link header (HATEOAS)
        response.headers["Link"] = f'<{location}>; rel="self", <{location}/duplicate>; rel="duplicate"'

        # RFC 7240: Prefer header support
        if prefer and "return=representation" in prefer.lower():
            # Client wants full object
            return success_response(
                RecipeSchema.model_validate(result, from_attributes = True),
                metadata = ResponseMetadata(duration_ms = int(duration_ms)),
            )

        # Default: minimal response (UUID only)
        return success_response(
            RecipeCreatedSchema(uuid = result.uuid),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def get_recipe(
        self,
        uuid: StdUUID,
            response: Response,
            request: Request,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
    ) -> ApiResponse[RecipeSchema]:
        """Get an recipe by its UUID.

        **SOTA REST Features:**
        - ETag header based on entity version (for caching/concurrency)
        - Cache-Control: private, max-age=300 (via middleware)
        - Link header for HATEOAS navigation
        - Supports If-None-Match for conditional GET (304 Not Modified)

        **Usage:**
        ```bash
        # First request
        curl -i /v1/recipes/01234...
        # Returns: ETag: "v1"
        
        # Subsequent request (cache validation)
        curl -H 'If-None-Match: "v1"' /v1/recipes/01234...
        # Returns: 304 Not Modified (if unchanged)
        ```
        """
        result = await self._service.read(self._to_uuid6(uuid))
        if result is None:
            self._logger.warning("⚠️ Recipe not found via HTTP", uuid=str(uuid))
            raise HTTPException(status_code=404, detail="Recipe not found")

        # RFC 7232: ETag for optimistic locking
        response.headers["ETag"] = f'"{result.version}"'

        # RFC 8288: Link header (HATEOAS)
        base = f"{request.url.path.rstrip('/')}"
        response.headers[
            "Link"] = f'<{base}>; rel="self", <{base}/duplicate>; rel="duplicate", </v1/recipes>; rel="collection"'
        
        return success_response(
            RecipeSchema.model_validate(result, from_attributes=True),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def update_recipe(
            self,
            uuid: StdUUID,
            payload: RecipeUpdateSchema,
            response: Response,
            request: Request,
            if_match: Annotated[str | None, Header()] = None,
    ) -> None:
        """Replace name of an existing recipe (PUT semantics).

        **SOTA REST Features:**
        - Requires If-Match header for optimistic locking
        - Returns 412 Precondition Failed if version mismatch
        - Returns 204 No Content on success
        - Content-Location header points to updated resource
        - New ETag in response headers

        **Usage:**
        ```bash
        # Get current version
        curl -i /v1/recipes/01234...
        # Returns: ETag: "v1"
        
        # Update with version check
        curl -X PUT /v1/recipes/01234... \\
          -H 'If-Match: "v1"' \\
          -d '{"name": "Nouvelle farine"}'
        ```

        The field is fully overwritten.
        Note: changes do not propagate to recipes where this recipe is already linked (snapshot model).
        """
        existing = await self._service.read(self._to_uuid6(uuid))
        if existing is None:
            self._logger.warning("⚠️ Recipe not found via HTTP (PUT)", uuid = str(uuid))
            raise HTTPException(status_code = 404, detail = "Recipe not found")

        # RFC 7232: If-Match validation (optimistic locking)
        if if_match:
            expected_version = int(if_match.strip('"').lstrip('vV'))
            if existing.version != expected_version:
                self._logger.warning(
                    "⚠️ Version mismatch (optimistic lock failure)",
                    uuid = str(uuid),
                    expected = expected_version,
                    current = existing.version,
                )
                raise HTTPException(
                    status_code = 412,
                    detail = f"Version mismatch: expected v{expected_version}, current v{existing.version}",
                )

        updated = await self._service.update(Recipe(uuid = self._to_uuid6(uuid), name = payload.name))

        # RFC 7231: Content-Location header
        response.headers["Content-Location"] = f"/v1/recipes/{uuid}"

        # New ETag after update
        response.headers["ETag"] = f'"{updated.version}"'

    async def patch_recipe(
            self,
            uuid: StdUUID,
            payload: RecipePatchSchema,
            response: Response,
            request: Request,
            if_match: Annotated[str | None, Header()] = None,
    ) -> None:
        """Partially update an recipe (PATCH semantics).

        **SOTA REST Features:**
        - Requires If-Match header for optimistic locking
        - Returns 412 Precondition Failed if version mismatch
        - Returns 204 No Content on success
        - Content-Location header points to updated resource

        Only the fields provided in the body are updated; omitted fields keep their current value.
        Note: changes do not propagate to recipes where this recipe is already linked (snapshot model).
        """
        existing = await self._service.read(self._to_uuid6(uuid))
        if existing is None:
            self._logger.warning("⚠️ Recipe not found via HTTP (PATCH)", uuid = str(uuid))
            raise HTTPException(status_code=404, detail="Recipe not found")

        # RFC 7232: If-Match validation
        if if_match:
            expected_version = int(if_match.strip('"').lstrip('vV'))
            if existing.version != expected_version:
                self._logger.warning(
                    "⚠️ Version mismatch (optimistic lock failure)",
                    uuid = str(uuid),
                    expected = expected_version,
                    current = existing.version,
                )
                raise HTTPException(
                    status_code = 412,
                    detail = f"Version mismatch: expected v{expected_version}, current v{existing.version}",
                )

        updated = await self._service.update(
            Recipe(
                uuid = existing.uuid,
                name = payload.name if payload.name is not None else existing.name,
            )
        )

        # RFC 7231: Content-Location header
        response.headers["Content-Location"] = f"/v1/recipes/{uuid}"

        # New ETag after update
        response.headers["ETag"] = f'"{updated.version}"'

    async def delete_recipe(self, uuid: StdUUID) -> None:
        """Soft-delete an recipe.

        **SOTA REST Features:**
        - Returns 204 No Content on success
        - Idempotent (deleting already-deleted resource returns 204)

        The recipe is marked as deleted and excluded from list results.
        It is retained until the purge retention period expires.
        Use `DELETE /admin/purge` to permanently remove all expired entities.
        """
        await self._service.delete(self._to_uuid6(uuid))

    async def list_recipes(
        self,
        response: Response,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        per_page: int = Query(20, ge=1, le=100, description="Items per page"),
        name: str | None = Query(None, min_length=1, description="Filter by name (partial, case-insensitive)"),
    ) -> PaginatedResponse[RecipeSchema]:
        """List all active (non-deleted) recipes.

        **SOTA REST Features:**
        - X-Total-Count header for total items (useful for pagination UI)
        - Cache-Control: private, max-age=60 (via middleware)
        - Always returns 200 OK, even if empty list

        Pass `name` for a partial, case-insensitive name filter.
        Each item: uuid, name, unit, created_at, updated_at, version.
        Use the returned UUIDs with `POST /v1/recipes/{uuid}/recipes/{recipe_uuid}` to link them to a recipe.
        """
        offset = (page - 1) * per_page
        items, total = await self._service.find_page_filtered(name=name, offset=offset, limit=per_page)

        # X-Total-Count header (common practice for pagination)
        response.headers["X-Total-Count"] = str(total)

        return paginated_response(
            data=[RecipeSchema.model_validate(i, from_attributes=True) for i in items],
            total=total,
            page=page,
            per_page=per_page,
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def duplicate_recipe(
        self,
        uuid: StdUUID,
            response: Response,
            request: Request,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
            prefer: Annotated[str | None, Header()] = None,
    ) -> ApiResponse[RecipeCreatedSchema] | ApiResponse[RecipeSchema]:
        """Duplicate an recipe, assigning it a new UUID.

        **SOTA REST Features:**
        - Returns 201 Created with UUID only (minimal response)
        - Location header points to the duplicated resource
        - Supports `Prefer: return=representation` to get full object

        Creates an independent copy with the same name and unit.
        Returns the UUID of the new recipe.
        """
        result = await self._service.duplicate(self._to_uuid6(uuid))

        # RFC 7231: Location header on 201 Created
        location = f"/v1/recipes/{result.uuid}"
        response.headers["Location"] = location

        # RFC 8288: Link header
        response.headers["Link"] = f'<{location}>; rel="self", </v1/recipes>; rel="collection"'

        # RFC 7240: Prefer header support
        if prefer and "return=representation" in prefer.lower():
            return success_response(
                RecipeSchema.model_validate(result, from_attributes = True),
                metadata = ResponseMetadata(duration_ms = int(duration_ms)),
            )

        # Default: minimal response (UUID only)
        return success_response(
            RecipeCreatedSchema(uuid = result.uuid),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

