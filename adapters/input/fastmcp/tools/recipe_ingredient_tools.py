import fastmcp
from arclith.domain.ports.logger import Logger
from pydantic import Field
from typing import Annotated
from uuid import UUID as StdUUID
from uuid6 import UUID

from adapters.input.fastmcp.dependencies import inject_tenant_uri
from adapters.input.schemas.ingredient_schema import IngredientSchema
from application.services.recipe_service import RecipeService


class RecipeIngredientMCP:
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
        async def link_ingredient_to_recipe(
                recipe_uuid: Annotated[
                    str, Field(description = "UUID (UUIDv7) de la recette à laquelle lier l'ingrédient.",
                               examples = ["01951234-5678-7abc-def0-123456789abc"])],
                ingredient_uuid: Annotated[str, Field(
                    description = "UUID (UUIDv7) de l'ingrédient existant à lier. L'ingrédient doit avoir été créé via `create_ingredient`.",
                    examples = ["01951234-5678-7abc-def0-123456789abc"])],
                ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Link an existing ingredient to a recipe.

            Copies the ingredient's data (name, unit, uuid) into the recipe at the time of linking.
            The original uuid is preserved to allow future synchronisation.
            Idempotent: if the ingredient is already linked, the call is silently ignored.
            Returns {"ingredient_uuid": "<uuid>"} on success, or {"error": "<message>"} if recipe or ingredient not found.
            Use `list_recipe_ingredients` to verify the current links.
            """
            await inject_tenant_uri(ctx)
            recipe = await service.read(to_uuid6(StdUUID(recipe_uuid)))
            if recipe is None:
                logger.warning("⚠️ Recipe not found via MCP", uuid = recipe_uuid)
                return {"error": "Recipe not found"}
            try:
                await service.add_ingredient(to_uuid6(StdUUID(recipe_uuid)), to_uuid6(StdUUID(ingredient_uuid)))
            except ValueError as e:
                logger.warning("⚠️ Ingredient not found via MCP", uuid = ingredient_uuid)
                return {"error": str(e)}
            return {"ingredient_uuid": ingredient_uuid}

        @self._mcp.tool
        async def unlink_ingredient_from_recipe(
                recipe_uuid: Annotated[str, Field(description = "UUID (UUIDv7) de la recette.",
                                                  examples = ["01951234-5678-7abc-def0-123456789abc"])],
                ingredient_uuid: Annotated[
                    str, Field(description = "UUID (UUIDv7) de l'ingrédient à délier de la recette.",
                               examples = ["01951234-5678-7abc-def0-123456789abc"])],
                ctx: fastmcp.Context | None = None,
        ) -> None:
            """Unlink an ingredient from a recipe.

            Removes the ingredient snapshot from the recipe's ingredient list.
            Silent no-op if the ingredient is not currently linked (idempotent).
            Does not affect the ingredient entity itself.
            """
            await inject_tenant_uri(ctx)
            recipe = await service.read(to_uuid6(StdUUID(recipe_uuid)))
            if recipe is None:
                logger.warning("⚠️ Recipe not found via MCP", uuid = recipe_uuid)
                return
            await service.remove_ingredient(to_uuid6(StdUUID(recipe_uuid)), to_uuid6(StdUUID(ingredient_uuid)))

        @self._mcp.tool
        async def list_recipe_ingredients(
                recipe_uuid: Annotated[
                    str, Field(description = "UUID (UUIDv7) de la recette dont on veut lister les ingrédients.",
                               examples = ["01951234-5678-7abc-def0-123456789abc"])],
                ctx: fastmcp.Context | None = None,
        ) -> list[dict]:
            """List all ingredients currently linked to a recipe.

            Returns the snapshot data as stored in the recipe at link time.
            Each item: uuid, name, unit, created_at, updated_at, version.
            Returns an empty list if the recipe is not found or has no linked ingredients.
            """
            await inject_tenant_uri(ctx)
            recipe = await service.read(to_uuid6(StdUUID(recipe_uuid)))
            if recipe is None:
                logger.warning("⚠️ Recipe not found via MCP", uuid = recipe_uuid)
                return []
            return [IngredientSchema.model_validate(i).model_dump() for i in (recipe.ingredients or [])]
