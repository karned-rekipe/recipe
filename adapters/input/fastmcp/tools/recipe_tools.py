import fastmcp
from arclith.domain.ports.logger import Logger
from pydantic import Field
from typing import Annotated, Literal
from uuid import UUID as StdUUID
from uuid6 import UUID

from adapters.input.fastmcp.dependencies import inject_tenant_uri
from adapters.input.schemas.recipe_schema import RecipeSchema
from application.services.recipe_service import RecipeService
from application.services.step_service import StepService
from domain.models.recipe import Recipe


class RecipeMCP:
    def __init__(self, service: RecipeService, step_service: StepService, logger: Logger, mcp: fastmcp.FastMCP) -> None:
        self._service = service
        self._step_service = step_service
        self._logger = logger
        self._mcp = mcp
        self._register_tools()

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    def _register_tools(self) -> None:
        service = self._service
        step_service = self._step_service
        logger = self._logger
        to_uuid6 = self._to_uuid6

        @self._mcp.tool
        async def create_recipe(
                name: Annotated[str, Field(description = "Nom de la recette. Sera normalisé (espaces rognés).",
                                           examples = ["Pizza Margherita", "Salade niçoise"])],
                description: Annotated[
                    str | None, Field(default = None, description = "Description libre de la recette.",
                                      examples = ["Une pizza classique italienne.", None])] = None,
                nutriscore: Annotated[Literal["A", "B", "C", "D", "E", "F"] | None, Field(default = None,
                                                                                          description = "Nutriscore de la recette (A = meilleur, F = moins bon). Omettre si inconnu.",
                                                                                          examples = ["A", "B",
                                                                                                      None])] = None,
                ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Create a new recipe (name, description, nutriscore).

            Returns the created recipe with its generated UUID.
            Workflow: after creation, attach content using:
              - `create_step` to add preparation steps
              - `link_ingredient_to_recipe` to link existing ingredients
              - `link_ustensil_to_recipe` to link existing ustensils
            Fields returned: uuid, name, description, nutriscore, ingredients, ustensils, steps, created_at, updated_at, version.
            """
            await inject_tenant_uri(ctx)
            result = await service.create(
                Recipe(name = name, description = description, nutriscore = nutriscore, ingredients = None,
                       ustensils = None, steps = None))
            return RecipeSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def get_recipe(
                uuid: Annotated[str, Field(description = "UUID (UUIDv7) de la recette à récupérer.",
                                           examples = ["01951234-5678-7abc-def0-123456789abc"])],
                ctx: fastmcp.Context | None = None,
        ) -> dict | None:
            """Get a recipe by its UUID.

            Returns the full recipe including all linked ingredients, ustensils and steps, or null if not found.
            Fields: uuid, name, description, nutriscore, ingredients (list), ustensils (list), steps (list), created_at, updated_at, version.
            """
            await inject_tenant_uri(ctx)
            result = await service.read(to_uuid6(StdUUID(uuid)))
            if result is None:
                logger.warning("⚠️ Recipe not found via MCP", uuid = uuid)
                return None
            steps = await step_service.find_by_recipe(to_uuid6(StdUUID(uuid)))
            result = result.model_copy(update = {"steps": steps or None})
            return RecipeSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def update_recipe(
                uuid: Annotated[str, Field(description = "UUID (UUIDv7) de la recette à modifier.",
                                           examples = ["01951234-5678-7abc-def0-123456789abc"])],
                name: Annotated[
                    str, Field(description = "Nouveau nom de la recette.", examples = ["Pizza Margherita revisitée"])],
                description: Annotated[str | None, Field(default = None,
                                                         description = "Nouvelle description. Passer null pour la supprimer.",
                                                         examples = ["Une pizza revisitée.", None])] = None,
                nutriscore: Annotated[Literal["A", "B", "C", "D", "E", "F"] | None, Field(default = None,
                                                                                          description = "Nouveau nutriscore. Passer null pour le supprimer.",
                                                                                          examples = ["B",
                                                                                                      None])] = None,
                ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Update name, description and nutriscore of a recipe.

            Full replacement (PUT semantics) for these three fields only.
            Does NOT affect linked ingredients, ustensils or steps.
            To manage links, use `link_ingredient_to_recipe`, `unlink_ingredient_from_recipe`,
            `link_ustensil_to_recipe`, `unlink_ustensil_from_recipe`, `create_step`, `delete_step`.
            Returns the updated recipe.
            """
            await inject_tenant_uri(ctx)
            result = await service.update(
                Recipe(uuid = to_uuid6(StdUUID(uuid)), name = name, description = description, nutriscore = nutriscore,
                       ingredients = None, ustensils = None, steps = None))
            return RecipeSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def delete_recipe(
                uuid: Annotated[str, Field(description = "UUID (UUIDv7) de la recette à supprimer.",
                                           examples = ["01951234-5678-7abc-def0-123456789abc"])],
                ctx: fastmcp.Context | None = None,
        ) -> None:
            """Soft-delete a recipe.

            The recipe is marked as deleted and excluded from list results.
            It is retained until the purge retention period expires.
            Use `purge_recipes` to permanently remove expired entries.
            """
            await inject_tenant_uri(ctx)
            await service.delete(to_uuid6(StdUUID(uuid)))

        @self._mcp.tool
        async def list_recipes(
                name: Annotated[str | None, Field(default = None,
                                                  description = "Filtre optionnel : recherche partielle sur le nom, insensible à la casse. Ex: 'pizza' retournera toutes les recettes dont le nom contient 'pizza'.",
                                                  examples = ["pizza", None])] = None,
                ctx: fastmcp.Context | None = None,
        ) -> list[dict]:
            """List all active (non-deleted) recipes.

            Pass `name` for a partial, case-insensitive name filter.
            Each recipe includes its full linked data: ingredients, ustensils and steps.
            Fields per item: uuid, name, description, nutriscore, ingredients, ustensils, steps, created_at, updated_at, version.
            """
            await inject_tenant_uri(ctx)
            items = await service.find_by_name(name) if name else await service.find_all()
            result = []
            for recipe in items:
                steps = await step_service.find_by_recipe(recipe.uuid)
                enriched = recipe.model_copy(update = {"steps": steps or None})
                result.append(RecipeSchema.model_validate(enriched).model_dump())
            return result

        @self._mcp.tool
        async def duplicate_recipe(
                uuid: Annotated[str, Field(description = "UUID (UUIDv7) de la recette à dupliquer.",
                                           examples = ["01951234-5678-7abc-def0-123456789abc"])],
                ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Duplicate a recipe, assigning it a new UUID.

            Creates a full copy including all linked ingredients, ustensils and steps.
            Returns the new recipe with its own UUID.
            """
            await inject_tenant_uri(ctx)
            result = await service.duplicate(to_uuid6(StdUUID(uuid)))
            return RecipeSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def purge_recipes(ctx: fastmcp.Context | None = None) -> dict:
            """Permanently delete soft-deleted recipes that have exceeded the retention period.

            Returns {"purged": <count>} with the number of permanently deleted records.
            This operation is irreversible.
            """
            await inject_tenant_uri(ctx)
            purged = await service.purge()
            return {"purged": purged}
