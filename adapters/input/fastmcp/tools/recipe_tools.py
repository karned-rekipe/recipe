import fastmcp
from pydantic import Field
from uuid6 import UUID

from adapters.input.fastmcp.dependencies import inject_tenant_uri, require_auth_mcp
from adapters.input.schemas.recipe_schema import RecipeSchema
from application.services.recipe_service import RecipeService
from arclith.domain.ports.logger import Logger
from domain.models.recipe import Recipe
from typing import Annotated
from uuid import UUID as StdUUID


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
                name: Annotated[str, Field(
                    description = "Nom de l'ingrédient (ex. 'Farine de blé', 'Sel fin'). Sera normalisé (espaces rognés).",
                    examples = ["Farine de blé", "Sel fin"])],
                ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Create a new reusable recipe.

            Returns the created recipe with its generated UUID.
            Once created, use `link_recipe_to_recipe` to attach it to a recipe.
            Fields returned: uuid, name, created_at, updated_at, version.
            """
            await require_auth_mcp(ctx)
            await inject_tenant_uri(ctx)
            result = await service.create(Recipe(name = name))
            logger.info("✅ Recipe created via MCP", uuid = str(result.uuid), name = result.name)
            return RecipeSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def get_recipe(
                uuid: Annotated[str, Field(description = "UUID (UUIDv7) de l'ingrédient à récupérer.",
                                           examples = ["01951234-5678-7abc-def0-123456789abc"])],
                ctx: fastmcp.Context | None = None,
        ) -> dict | None:
            """Get an recipe by its UUID.

            Returns the full recipe object or null if not found.
            Fields: uuid, name, created_at, updated_at, version.
            """
            await inject_tenant_uri(ctx)
            result = await service.read(to_uuid6(StdUUID(uuid)))
            if result is None:
                logger.warning("⚠️ Recipe not found via MCP", uuid = uuid)
                return None
            logger.info("✅ Recipe fetched via MCP", uuid = uuid, name = result.name)
            return RecipeSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def update_recipe(
                uuid: Annotated[str, Field(description = "UUID (UUIDv7) de l'ingrédient à modifier.",
                                           examples = ["01951234-5678-7abc-def0-123456789abc"])],
                name: Annotated[str, Field(description = "Nouveau nom de l'ingrédient.",
                                           examples = ["Farine complète", "Gros sel"])],
                ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Replace name of an existing recipe.

            Full replacement (PUT semantics): name is overwritten.
            Returns the updated recipe.
            Note: updating an recipe does not propagate to recipes where it is already linked (snapshot model).
            """
            await inject_tenant_uri(ctx)
            result = await service.update(Recipe(uuid = to_uuid6(StdUUID(uuid)), name = name))
            logger.info("✅ Recipe updated via MCP", uuid = uuid, name = result.name)
            return RecipeSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def delete_recipe(
                uuid: Annotated[str, Field(description = "UUID (UUIDv7) de l'ingrédient à supprimer.",
                                           examples = ["01951234-5678-7abc-def0-123456789abc"])],
                ctx: fastmcp.Context | None = None,
        ) -> None:
            """Soft-delete an recipe.

            The recipe is marked as deleted and excluded from list results.
            It is retained until the purge retention period expires.
            Use `purge_recipes` to permanently remove expired entries.
            """
            await require_auth_mcp(ctx)
            await inject_tenant_uri(ctx)
            await service.delete(to_uuid6(StdUUID(uuid)))
            logger.info("✅ Recipe deleted via MCP", uuid = uuid)

        @self._mcp.tool
        async def list_recipes(
                name: Annotated[str | None, Field(default = None,
                                                  description = "Filtre optionnel : recherche partielle sur le nom, insensible à la casse. Ex: 'far' retournera 'Farine de blé'.",
                                                  examples = ["farine", None])] = None,
                ctx: fastmcp.Context | None = None,
        ) -> list[dict]:
            """List all active (non-deleted) recipes.

            Pass `name` for a partial, case-insensitive name filter.
            Each item: uuid, name, created_at, updated_at, version.
            Use these UUIDs with `link_recipe_to_recipe` to attach recipes to a recipe.
            """
            await inject_tenant_uri(ctx)
            items = await service.find_by_name(name) if name else await service.find_all()
            logger.info("✅ Recipes listed via MCP", count = len(items), filter = name)
            return [RecipeSchema.model_validate(i).model_dump() for i in items]

        @self._mcp.tool
        async def duplicate_recipe(
                uuid: Annotated[str, Field(description = "UUID (UUIDv7) de l'ingrédient à dupliquer.",
                                           examples = ["01951234-5678-7abc-def0-123456789abc"])],
                ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Duplicate an recipe, assigning it a new UUID.

            Creates an independent copy with the same name.
            Returns the new recipe with its own UUID.
            """
            await inject_tenant_uri(ctx)
            result = await service.duplicate(to_uuid6(StdUUID(uuid)))
            logger.info("✅ Recipe duplicated via MCP", source_uuid = uuid, new_uuid = str(result.uuid))
            return RecipeSchema.model_validate(result).model_dump()

