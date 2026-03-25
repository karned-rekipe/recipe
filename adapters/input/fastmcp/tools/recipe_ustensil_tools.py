import fastmcp
from arclith.domain.ports.logger import Logger
from pydantic import Field
from typing import Annotated
from uuid import UUID as StdUUID
from uuid6 import UUID

from adapters.input.fastmcp.dependencies import inject_tenant_uri
from adapters.input.schemas.ustensil_schema import UstensilSchema
from application.services.recipe_service import RecipeService


class RecipeUstensilMCP:
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
        async def link_ustensil_to_recipe(
                recipe_uuid: Annotated[
                    str, Field(description = "UUID (UUIDv7) de la recette à laquelle lier l'ustensile.",
                               examples = ["01951234-5678-7abc-def0-123456789abc"])],
                ustensil_uuid: Annotated[str, Field(
                    description = "UUID (UUIDv7) de l'ustensile existant à lier. L'ustensile doit avoir été créé via `create_ustensil`.",
                    examples = ["01951234-5678-7abc-def0-123456789abc"])],
                ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Link an existing ustensil to a recipe.

            Copies the ustensil's data (name, uuid) into the recipe at the time of linking.
            The original uuid is preserved to allow future synchronisation.
            Idempotent: if the ustensil is already linked, the call is silently ignored.
            Returns {"ustensil_uuid": "<uuid>"} on success, or {"error": "<message>"} if recipe or ustensil not found.
            Use `list_recipe_ustensils` to verify the current links.
            """
            await inject_tenant_uri(ctx)
            recipe = await service.read(to_uuid6(StdUUID(recipe_uuid)))
            if recipe is None:
                logger.warning("⚠️ Recipe not found via MCP", uuid = recipe_uuid)
                return {"error": "Recipe not found"}
            try:
                await service.add_ustensil(to_uuid6(StdUUID(recipe_uuid)), to_uuid6(StdUUID(ustensil_uuid)))
            except ValueError as e:
                logger.warning("⚠️ Ustensil not found via MCP", uuid = ustensil_uuid)
                return {"error": str(e)}
            return {"ustensil_uuid": ustensil_uuid}

        @self._mcp.tool
        async def unlink_ustensil_from_recipe(
                recipe_uuid: Annotated[str, Field(description = "UUID (UUIDv7) de la recette.",
                                                  examples = ["01951234-5678-7abc-def0-123456789abc"])],
                ustensil_uuid: Annotated[
                    str, Field(description = "UUID (UUIDv7) de l'ustensile à délier de la recette.",
                               examples = ["01951234-5678-7abc-def0-123456789abc"])],
                ctx: fastmcp.Context | None = None,
        ) -> None:
            """Unlink an ustensil from a recipe.

            Removes the ustensil snapshot from the recipe's ustensil list.
            Silent no-op if the ustensil is not currently linked (idempotent).
            Does not affect the ustensil entity itself.
            """
            await inject_tenant_uri(ctx)
            recipe = await service.read(to_uuid6(StdUUID(recipe_uuid)))
            if recipe is None:
                logger.warning("⚠️ Recipe not found via MCP", uuid = recipe_uuid)
                return
            await service.remove_ustensil(to_uuid6(StdUUID(recipe_uuid)), to_uuid6(StdUUID(ustensil_uuid)))

        @self._mcp.tool
        async def list_recipe_ustensils(
                recipe_uuid: Annotated[
                    str, Field(description = "UUID (UUIDv7) de la recette dont on veut lister les ustensiles.",
                               examples = ["01951234-5678-7abc-def0-123456789abc"])],
                ctx: fastmcp.Context | None = None,
        ) -> list[dict]:
            """List all ustensils currently linked to a recipe.

            Returns the snapshot data as stored in the recipe at link time.
            Each item: uuid, name, created_at, updated_at, version.
            Returns an empty list if the recipe is not found or has no linked ustensils.
            """
            await inject_tenant_uri(ctx)
            recipe = await service.read(to_uuid6(StdUUID(recipe_uuid)))
            if recipe is None:
                logger.warning("⚠️ Recipe not found via MCP", uuid = recipe_uuid)
                return []
            return [UstensilSchema.model_validate(u).model_dump() for u in (recipe.ustensils or [])]
