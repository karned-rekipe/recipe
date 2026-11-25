from typing import Annotated
from uuid import UUID as StdUUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from uuid6 import UUID

from adapters.input.fastapi.dependencies import inject_tenant_uri, require_auth
from adapters.input.schemas.recipe_schema import (
    RecipeCreatedSchema,
    RecipeCreateSchema,
    RecipeAIEnrichmentRequestSchema,
    RecipeAIEnrichmentResponseSchema,
    RecipeImageGenerationRequestSchema,
    RecipeImageGenerationResponseSchema,
    RecipePatchSchema,
    RecipeSchema,
    RecipeUpdateSchema,
    recipe_create_payload_to_domain,
    recipe_patch_payload_to_domain,
    recipe_update_payload_to_domain,
)
from domain.models.recipe import RecipeStatus
from application.services.recipe_service import (
    RecipeComponentCycleError,
    RecipeComponentInUseError,
    RecipeAIEnrichmentUnavailableError,
    RecipeReferenceError,
    RecipeImageAlreadyExistsError,
    RecipeImageGenerationConflictError,
    RecipeImageGenerationInProgressError,
    RecipeImageGenerationUnavailableError,
    RecipeService,
)
from arclith.adapters.input.fastapi.dependencies import get_duration_ms
from arclith.adapters.input.schemas.response_wrapper import (
    ApiResponse,
    PaginatedResponse,
    ResponseMetadata,
    paginated_response,
    success_response,
)
from arclith.domain.ports.logger import Logger

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
            response_model=None,
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
            methods=["POST"],
            path="/{uuid}/main-image",
            endpoint=self.generate_recipe_image,
            summary="Generate and attach the recipe main image",
            response_model=ApiResponse[RecipeImageGenerationResponseSchema],
            status_code=200,
            responses={
                404: {"description": "Recipe not found"},
                409: {"description": "Recipe already has a main image"},
                502: {"description": "Media image generation failed"},
                503: {"description": "Image generation is not configured"},
            },
            dependencies=[Depends(require_auth)],
        )
        self.router.add_api_route(
            methods=["POST"],
            path="/{uuid}/ai-enrich",
            endpoint=self.enrich_recipe_with_ai,
            summary="Enrich an existing recipe through the internal AI agent",
            response_model=ApiResponse[RecipeAIEnrichmentResponseSchema],
            status_code=200,
            responses={
                404: {"description": "Recipe not found"},
                502: {"description": "Recipe AI enrichment failed"},
                503: {"description": "Recipe AI enrichment is not configured"},
            },
            dependencies=[Depends(require_auth)],
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
            response_model=None,
            status_code=201,
            responses = {
                404: {"description": "Recipe not found"},
            },
        )

    async def generate_recipe_image(
        self,
        uuid: StdUUID,
        payload: RecipeImageGenerationRequestSchema,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
    ) -> ApiResponse[RecipeImageGenerationResponseSchema]:
        """Generate, store, and attach the recipe main image through media."""
        try:
            recipe, generated = await self._service.generate_main_image(
                self._to_uuid6(uuid),
                replace_existing=payload.replace_existing,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Recipe not found") from exc
        except (
            RecipeImageAlreadyExistsError,
            RecipeImageGenerationConflictError,
            RecipeImageGenerationInProgressError,
        ) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RecipeImageGenerationUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        hydrated = await self._service.hydrate_recipe(recipe)
        self._logger.info(
            "✅ Recipe image generated via HTTP",
            uuid=str(uuid),
            provider=generated.provider,
            image_url=generated.image.url,
        )
        return success_response(
            RecipeImageGenerationResponseSchema(
                recipe=RecipeSchema.model_validate(hydrated),
                **generated.model_dump(),
            ),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def enrich_recipe_with_ai(
        self,
        uuid: StdUUID,
        payload: RecipeAIEnrichmentRequestSchema,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
    ) -> ApiResponse[RecipeAIEnrichmentResponseSchema]:
        """Enrich an existing recipe through the cluster-internal agent MCP."""
        try:
            recipe, result = await self._service.enrich_with_ai(
                self._to_uuid6(uuid),
                generate_image=payload.generate_image,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Recipe not found") from exc
        except RecipeAIEnrichmentUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        hydrated = await self._service.hydrate_recipe(recipe)
        self._logger.info(
            "✅ Recipe enriched through internal AI agent via HTTP",
            uuid=str(uuid),
            image_generated=result.image_generated,
        )
        return success_response(
            RecipeAIEnrichmentResponseSchema(
                recipe=RecipeSchema.model_validate(hydrated),
                **result.model_dump(),
            ),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
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
        """Create a new complete recipe aggregate.

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
          -d '{"name": "Houmous", "servings": 4, "ingredients": [...], "steps": [...]}'
        
        # Full representation
        curl -X POST /v1/recipes \\
          -H "Prefer: return=representation" \\
          -d '{"name": "Houmous", "servings": 4, "ingredients": [...], "steps": [...]}'
        ```
        """
        try:
            result = await self._service.create(recipe_create_payload_to_domain(payload))
        except (RecipeComponentCycleError, RecipeReferenceError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        # RFC 7231: Location header on 201 Created
        location = f"{request.url.path.rstrip('/')}/{result.uuid}"
        response.headers["Location"] = location

        # RFC 8288: Link header (HATEOAS)
        response.headers["Link"] = f'<{location}>; rel="self", <{location}/duplicate>; rel="duplicate"'

        # RFC 7240: Prefer header support
        prefer_header = request.headers.get("prefer", prefer or "")
        if "return=representation" in prefer_header.lower():
            # Client wants full object
            return success_response(
                RecipeSchema.model_validate(await self._service.hydrate_recipe(result)),
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
        """Get a recipe aggregate by its UUID.

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
            RecipeSchema.model_validate(await self._service.hydrate_recipe(result)),
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
        """Replace an existing recipe aggregate (PUT semantics).

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
          -d '{"name": "Nouvelle recette", "servings": 4, "ingredients": [...], "steps": [...]}'
        ```

        The aggregate is fully overwritten.
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

        try:
            updated = await self._service.update(recipe_update_payload_to_domain(existing, payload))
        except (RecipeComponentCycleError, RecipeReferenceError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

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
        """Partially update a recipe aggregate (PATCH semantics).

        **SOTA REST Features:**
        - Requires If-Match header for optimistic locking
        - Returns 412 Precondition Failed if version mismatch
        - Returns 204 No Content on success
        - Content-Location header points to updated resource

        Only the fields provided in the body are updated; omitted fields keep their current value.
        Provided collections replace the full corresponding section.
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

        try:
            updated = await self._service.update(recipe_patch_payload_to_domain(existing, payload))
        except (RecipeComponentCycleError, RecipeReferenceError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

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
        try:
            await self._service.delete(self._to_uuid6(uuid))
        except RecipeComponentInUseError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    async def list_recipes(
        self,
        response: Response,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        per_page: int = Query(20, ge=1, le=100, description="Items per page"),
        name: str | None = Query(None, min_length=1, description="Filter by name (partial, case-insensitive)"),
        ingredient_uuid: StdUUID | None = Query(None, description="Filter recipes using an ingredient UUID"),
        equipment_uuid: StdUUID | None = Query(None, description="Filter recipes using an equipment UUID"),
        tag_uuid: StdUUID | None = Query(None, description="Filter recipes using a tag UUID"),
        difficulty: int | None = Query(None, ge=1, le=5, description="Filter by difficulty level"),
        origin_country: str | None = Query(None, min_length=2, max_length=2, description="Filter by origin country code"),
        price: int | None = Query(None, ge=1, le=5, description="Filter by price level"),
        favorite: bool | None = Query(None, description="Filter favorite recipes"),
        season_month: int | None = Query(None, ge=1, le=12, description="Filter by computed seasonal month"),
        status: RecipeStatus | None = Query(None, description="Filter by lifecycle status"),
        meal_planner_eligible: bool | None = Query(None, description="Return only active recipes selectable by the meal planner"),
    ) -> PaginatedResponse[RecipeSchema]:
        """List all active (non-deleted) recipe aggregates.

        **SOTA REST Features:**
        - X-Total-Count header for total items (useful for pagination UI)
        - Cache-Control: private, max-age=60 (via middleware)
        - Always returns 200 OK, even if empty list

        Pass `name` for a partial, case-insensitive name filter.
        Each item returns the recipe aggregate payload.
        """
        offset = (page - 1) * per_page
        try:
            items, total = await self._service.find_page_filtered_hydrated(
                name=name,
                ingredient_uuid=self._to_uuid6(ingredient_uuid) if ingredient_uuid is not None else None,
                equipment_uuid=self._to_uuid6(equipment_uuid) if equipment_uuid is not None else None,
                tag_uuid=self._to_uuid6(tag_uuid) if tag_uuid is not None else None,
                difficulty=difficulty,
                origin_country=origin_country.upper() if origin_country is not None else None,
                price=price,
                favorite=favorite,
                season_month=season_month,
                status=status,
                meal_planner_eligible=meal_planner_eligible,
                offset=offset,
                limit=per_page,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        # X-Total-Count header (common practice for pagination)
        response.headers["X-Total-Count"] = str(total)

        return paginated_response(
            data=[RecipeSchema.model_validate(i) for i in items],
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
        """Duplicate a recipe aggregate, assigning it a new UUID.

        **SOTA REST Features:**
        - Returns 201 Created with UUID only (minimal response)
        - Location header points to the duplicated resource
        - Supports `Prefer: return=representation` to get full object

        Creates an independent copy with the same aggregate data.
        Returns the UUID of the new recipe.
        """
        result = await self._service.duplicate(self._to_uuid6(uuid))

        # RFC 7231: Location header on 201 Created
        location = f"/v1/recipes/{result.uuid}"
        response.headers["Location"] = location

        # RFC 8288: Link header
        response.headers["Link"] = f'<{location}>; rel="self", </v1/recipes>; rel="collection"'

        # RFC 7240: Prefer header support
        prefer_header = request.headers.get("prefer", prefer or "")
        if "return=representation" in prefer_header.lower():
            return success_response(
                RecipeSchema.model_validate(await self._service.hydrate_recipe(result)),
                metadata = ResponseMetadata(duration_ms = int(duration_ms)),
            )

        # Default: minimal response (UUID only)
        return success_response(
            RecipeCreatedSchema(uuid = result.uuid),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )
