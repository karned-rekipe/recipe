from typing import Annotated
from uuid import UUID as StdUUID
from uuid6 import UUID

import fastmcp
from pydantic import Field

from adapters.input.fastmcp.dependencies import inject_tenant_uri
from adapters.input.schemas.recipe_schema import RecipeSchema
from application.services.recipe_service import RecipeService
from arclith.domain.ports.logger import Logger
from domain.models.recipe import Recipe


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
            name: Annotated[str, Field(description="Nom de l'ingrédient.", examples=["Farine de blé"])],
            unit: Annotated[str | None, Field(default=None, description="Unité de mesure (ex. g, kg, ml). None si non applicable.", examples=["g", "kg", None])] = None,
            ctx: fastmcp.Context = None,
        ) -> dict:
            """Create a new recipe."""
            await inject_tenant_uri(ctx)
            result = await service.create(Recipe(name=name, unit=unit))
            return RecipeSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def get_recipe(
            uuid: Annotated[str, Field(description="UUID de l'ingrédient.", examples=["01951234-5678-7abc-def0-123456789abc"])],
            ctx: fastmcp.Context = None,
        ) -> dict | None:
            """Get an recipe by its UUID."""
            await inject_tenant_uri(ctx)
            result = await service.read(to_uuid6(StdUUID(uuid)))
            if result is None:
                logger.warning("⚠️ Recipe not found via MCP", uuid=uuid)
                return None
            return RecipeSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def update_recipe(
            uuid: Annotated[str, Field(description="UUID de l'ingrédient à modifier.", examples=["01951234-5678-7abc-def0-123456789abc"])],
            name: Annotated[str, Field(description="Nouveau nom de l'ingrédient.", examples=["Farine complète"])],
            unit: Annotated[str | None, Field(default=None, description="Nouvelle unité de mesure.", examples=["g", None])] = None,
            ctx: fastmcp.Context = None,
        ) -> dict:
            """Update an existing recipe."""
            await inject_tenant_uri(ctx)
            result = await service.update(Recipe(uuid=to_uuid6(StdUUID(uuid)), name=name, unit=unit))
            return RecipeSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def delete_recipe(
            uuid: Annotated[str, Field(description="UUID de l'ingrédient à supprimer.", examples=["01951234-5678-7abc-def0-123456789abc"])],
            ctx: fastmcp.Context = None,
        ) -> None:
            """Delete an recipe by its UUID."""
            await inject_tenant_uri(ctx)
            await service.delete(to_uuid6(StdUUID(uuid)))

        @self._mcp.tool
        async def list_recipes(
            name: Annotated[str | None, Field(default=None, description="Filtre par nom (recherche partielle, insensible à la casse).", examples=["farine", None])] = None,
            ctx: fastmcp.Context = None,
        ) -> list[dict]:
            """List all recipes, optionally filtered by name."""
            await inject_tenant_uri(ctx)
            items = await service.find_by_name(name) if name else await service.find_all()
            return [RecipeSchema.model_validate(i).model_dump() for i in items]

        @self._mcp.tool
        async def duplicate_recipe(
            uuid: Annotated[str, Field(description="UUID de l'ingrédient à dupliquer.", examples=["01951234-5678-7abc-def0-123456789abc"])],
            ctx: fastmcp.Context = None,
        ) -> dict:
            """Duplicate an recipe, assigning it a new UUID."""
            await inject_tenant_uri(ctx)
            result = await service.duplicate(to_uuid6(StdUUID(uuid)))
            return RecipeSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def purge_recipes(ctx: fastmcp.Context = None) -> dict:
            """Purge all soft-deleted recipes that have exceeded the retention period."""
            await inject_tenant_uri(ctx)
            purged = await service.purge()
            return {"purged": purged}

