from typing import Annotated
from uuid import UUID as StdUUID

import fastmcp
from pydantic import Field
from uuid6 import UUID

from adapters.input.fastmcp.dependencies import inject_tenant_uri, require_auth_mcp
from adapters.input.schemas.recipe_schema import (
    RecipeCreateSchema,
    RecipePatchSchema,
    RecipeSchema,
    RecipeUpdateSchema,
    recipe_create_payload_to_domain,
    recipe_patch_payload_to_domain,
    recipe_update_payload_to_domain,
)
from application.services.recipe_service import RecipeService
from arclith.domain.ports.logger import Logger


class RecipeMCP:
    def __init__(self, service: RecipeService, logger: Logger, mcp: fastmcp.FastMCP) -> None:
        self._service = service
        self._logger = logger
        self._mcp = mcp
        self._register_tools()

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    def _register_tools(self) -> None:
        service = self._service
        logger = self._logger
        to_uuid6 = self._to_uuid6

        @self._mcp.tool
        async def create_recipe(
            payload: Annotated[
                dict,
                Field(
                    description="Complete recipe payload with servings, ingredients, equipment, steps, sources, and image URIs.",
                    examples=[{
                        "name": "Houmous maison",
                        "servings": 4,
                        "ingredients": [{
                            "ingredient_uuid": "01951234-5678-7abc-def0-123456789abc",
                            "quantity": 400,
                            "unit": "g",
                        }],
                        "equipment": [{"equipment_uuid": "01951234-5678-7abc-def0-123456789abd"}],
                        "steps": [{
                            "name": "Mixer",
                            "description": "Mixer tous les ingredients.",
                            "rank": 1,
                            "secondary_images": [],
                        }],
                    }],
                ),
            ],
            ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Create a complete recipe aggregate.

            The payload is the same complete aggregate expected by the HTTP API.
            Returns the created recipe aggregate.
            """
            await require_auth_mcp(ctx)
            await inject_tenant_uri(ctx)
            validated = RecipeCreateSchema.model_validate(payload)
            result = await service.create(recipe_create_payload_to_domain(validated))
            logger.info("✅ Recipe created via MCP", uuid=str(result.uuid), name=result.name)
            return RecipeSchema.model_validate(await service.hydrate_recipe(result)).model_dump(mode="json")

        @self._mcp.tool
        async def get_recipe(
            uuid: Annotated[
                str,
                Field(
                    description="UUID (UUIDv7) of the recipe to retrieve.",
                    examples=["01951234-5678-7abc-def0-123456789abc"],
                ),
            ],
            ctx: fastmcp.Context | None = None,
        ) -> dict | None:
            """Get a recipe aggregate by its UUID."""
            await inject_tenant_uri(ctx)
            result = await service.read(to_uuid6(StdUUID(uuid)))
            if result is None:
                logger.warning("⚠️ Recipe not found via MCP", uuid=uuid)
                return None
            logger.info("✅ Recipe fetched via MCP", uuid=uuid, name=result.name)
            return RecipeSchema.model_validate(await service.hydrate_recipe(result)).model_dump(mode="json")

        @self._mcp.tool
        async def update_recipe(
            uuid: Annotated[
                str,
                Field(
                    description="UUID (UUIDv7) of the recipe to replace.",
                    examples=["01951234-5678-7abc-def0-123456789abc"],
                ),
            ],
            payload: Annotated[
                dict,
                Field(
                    description="Full replacement recipe payload. Omitted collections are replaced with their default values.",
                ),
            ],
            ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Replace a recipe aggregate (PUT semantics)."""
            await inject_tenant_uri(ctx)
            existing = await service.read(to_uuid6(StdUUID(uuid)))
            if existing is None:
                logger.warning("⚠️ Recipe not found via MCP (PUT)", uuid=uuid)
                raise KeyError(f"Recipe with uuid {uuid} not found")
            validated = RecipeUpdateSchema.model_validate(payload)
            result = await service.update(recipe_update_payload_to_domain(existing, validated))
            logger.info("✅ Recipe updated via MCP", uuid=uuid, name=result.name)
            return RecipeSchema.model_validate(await service.hydrate_recipe(result)).model_dump(mode="json")

        @self._mcp.tool
        async def patch_recipe(
            uuid: Annotated[
                str,
                Field(
                    description="UUID (UUIDv7) of the recipe to partially update.",
                    examples=["01951234-5678-7abc-def0-123456789abc"],
                ),
            ],
            payload: Annotated[
                dict,
                Field(
                    description="Partial recipe payload. Provided collections replace the whole corresponding section.",
                ),
            ],
            ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Partially update a recipe aggregate (PATCH semantics)."""
            await inject_tenant_uri(ctx)
            existing = await service.read(to_uuid6(StdUUID(uuid)))
            if existing is None:
                logger.warning("⚠️ Recipe not found via MCP (PATCH)", uuid=uuid)
                raise KeyError(f"Recipe with uuid {uuid} not found")
            validated = RecipePatchSchema.model_validate(payload)
            result = await service.update(recipe_patch_payload_to_domain(existing, validated))
            logger.info("✅ Recipe patched via MCP", uuid=uuid, name=result.name)
            return RecipeSchema.model_validate(await service.hydrate_recipe(result)).model_dump(mode="json")

        @self._mcp.tool
        async def delete_recipe(
            uuid: Annotated[
                str,
                Field(
                    description="UUID (UUIDv7) of the recipe to delete.",
                    examples=["01951234-5678-7abc-def0-123456789abc"],
                ),
            ],
            ctx: fastmcp.Context | None = None,
        ) -> None:
            """Soft-delete a recipe aggregate."""
            await require_auth_mcp(ctx)
            await inject_tenant_uri(ctx)
            await service.delete(to_uuid6(StdUUID(uuid)))
            logger.info("✅ Recipe deleted via MCP", uuid=uuid)

        @self._mcp.tool
        async def list_recipes(
            name: Annotated[
                str | None,
                Field(
                    default=None,
                    description="Optional partial name filter, case-insensitive.",
                    examples=["houmous", None],
                ),
            ] = None,
            ctx: fastmcp.Context | None = None,
        ) -> list[dict]:
            """List all active recipe aggregates."""
            await inject_tenant_uri(ctx)
            items = await service.find_by_name(name) if name else await service.find_all()
            hydrated = await service.hydrate_recipes(items)
            logger.info("✅ Recipes listed via MCP", count=len(items), filter=name)
            return [RecipeSchema.model_validate(i).model_dump(mode="json") for i in hydrated]

        @self._mcp.tool
        async def duplicate_recipe(
            uuid: Annotated[
                str,
                Field(
                    description="UUID (UUIDv7) of the recipe to duplicate.",
                    examples=["01951234-5678-7abc-def0-123456789abc"],
                ),
            ],
            ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Duplicate a recipe aggregate, assigning it a new UUID."""
            await inject_tenant_uri(ctx)
            result = await service.duplicate(to_uuid6(StdUUID(uuid)))
            logger.info("✅ Recipe duplicated via MCP", source_uuid=uuid, new_uuid=str(result.uuid))
            return RecipeSchema.model_validate(await service.hydrate_recipe(result)).model_dump(mode="json")
