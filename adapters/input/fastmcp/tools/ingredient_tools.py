import fastmcp
from pydantic import Field
from uuid6 import UUID

from adapters.input.fastmcp.dependencies import inject_tenant_uri, require_auth_mcp
from adapters.input.schemas.ingredient_schema import IngredientSchema
from adapters.input.schemas.recipe_schema import RecipeSchema
from application.services.ingredient_service import IngredientService
from application.services.recipe_service import RecipeService
from arclith.domain.ports.logger import Logger
from domain.models.ingredient import Ingredient
from typing import Annotated
from uuid import UUID as StdUUID


class IngredientMCP:
    def __init__(
            self,
            service: IngredientService,
            logger: Logger,
            mcp: fastmcp.FastMCP,
            recipe_service: RecipeService | None = None,
    ) -> None:
        self._service = service
        self._logger = logger
        self._mcp = mcp
        self._recipe_service = recipe_service
        self._register_tools()

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    def _register_tools(self) -> None:
        service = self._service
        logger = self._logger
        recipe_service = self._recipe_service
        to_uuid6 = self._to_uuid6

        @self._mcp.tool
        async def create_ingredient(
                name: Annotated[str, Field(
                    description="Ingredient name (e.g. 'Tomate', 'Farine de blé'). Will be normalized (spaces trimmed).",
                    examples=["Tomate", "Farine de blé"])],
                rayon_uuid: Annotated[str | None, Field(default=None, description="Shelf/aisle UUID.")] = None,
                group_uuid: Annotated[str | None, Field(default=None, description="Food group UUID.")] = None,
                green_score: Annotated[int | None, Field(default=None, description="Environmental score (OpenFoodFacts scale, ≥0).", examples=[80])] = None,
                unit: Annotated[str | None, Field(default=None, description="Unit of measure.", examples=["g", "ml", "pièce"])] = None,
                quantity: Annotated[float | None, Field(default=None, description="Default quantity (≥0).", examples=[100.0])] = None,
                season_months: Annotated[dict[int, int], Field(description="Seasonality map: month (1-12) → score (1-3), 3=peak season.", examples=[{6: 2, 7: 3, 8: 3, 9: 2}])] = {},
                ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Create a new ingredient.

            Returns the created ingredient with its generated UUID.
            Fields returned: uuid, name, rayon, group, green_score, unit, quantity, season_months, created_at, updated_at, version.
            """
            await require_auth_mcp(ctx)
            await inject_tenant_uri(ctx)
            result = await service.create(Ingredient(
                name=name,
                rayon_uuid=to_uuid6(StdUUID(rayon_uuid)) if rayon_uuid else None,
                group_uuid=to_uuid6(StdUUID(group_uuid)) if group_uuid else None,
                green_score=green_score,
                unit=unit,
                quantity=quantity,
                season_months=season_months,
            ))
            logger.info("✅ Ingredient created via MCP", uuid=str(result.uuid), name=result.name)
            return IngredientSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def get_ingredient(
                uuid: Annotated[str, Field(description="UUID (UUIDv7) of the ingredient to retrieve.",
                                           examples=["01951234-5678-7abc-def0-123456789abc"])],
                ctx: fastmcp.Context | None = None,
        ) -> dict | None:
            """Get an ingredient by its UUID.

            Returns the full ingredient object or null if not found.
            """
            await inject_tenant_uri(ctx)
            result = await service.read(to_uuid6(StdUUID(uuid)))
            if result is None:
                logger.warning("⚠️ Ingredient not found via MCP", uuid=uuid)
                return None
            logger.info("✅ Ingredient fetched via MCP", uuid=uuid, name=result.name)
            return IngredientSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def update_ingredient(
                uuid: Annotated[str, Field(description="UUID (UUIDv7) of the ingredient to update.",
                                           examples=["01951234-5678-7abc-def0-123456789abc"])],
                name: Annotated[str, Field(description="New ingredient name.", examples=["Farine complète"])],
                rayon_uuid: Annotated[str | None, Field(default=None, description="Shelf/aisle UUID.")] = None,
                group_uuid: Annotated[str | None, Field(default=None, description="Food group UUID.")] = None,
                green_score: Annotated[int | None, Field(default=None, description="Environmental score.")] = None,
                unit: Annotated[str | None, Field(default=None, description="Unit of measure.")] = None,
                quantity: Annotated[float | None, Field(default=None, description="Default quantity.")] = None,
                season_months: Annotated[dict[int, int], Field(description="Seasonality map.")] = {},
                ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Replace an existing ingredient (PUT semantics).

            Full replacement: all fields are overwritten.
            Returns the updated ingredient.
            """
            await inject_tenant_uri(ctx)
            result = await service.update(Ingredient(
                uuid=to_uuid6(StdUUID(uuid)),
                name=name,
                rayon_uuid=to_uuid6(StdUUID(rayon_uuid)) if rayon_uuid else None,
                group_uuid=to_uuid6(StdUUID(group_uuid)) if group_uuid else None,
                green_score=green_score,
                unit=unit,
                quantity=quantity,
                season_months=season_months,
            ))
            logger.info("✅ Ingredient updated via MCP", uuid=uuid, name=result.name)
            return IngredientSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def delete_ingredient(
                uuid: Annotated[str, Field(description="UUID (UUIDv7) of the ingredient to delete.",
                                           examples=["01951234-5678-7abc-def0-123456789abc"])],
                ctx: fastmcp.Context | None = None,
        ) -> None:
            """Soft-delete an ingredient.

            The ingredient is marked as deleted and excluded from list results.
            It is retained until the purge retention period expires.
            Use `purge_ingredients` to permanently remove expired entries.
            """
            await require_auth_mcp(ctx)
            await inject_tenant_uri(ctx)
            ingredient_uuid = to_uuid6(StdUUID(uuid))
            if recipe_service is not None and await recipe_service.is_ingredient_used(ingredient_uuid):
                raise ValueError("Ingredient is used by at least one recipe")
            await service.delete(ingredient_uuid)
            logger.info("✅ Ingredient deleted via MCP", uuid=uuid)

        @self._mcp.tool
        async def list_ingredients(
                name: Annotated[str | None, Field(default=None,
                                                  description="Optional partial name filter, case-insensitive. E.g. 'tom' will return 'Tomate'.",
                                                  examples=["tomate", None])] = None,
                ctx: fastmcp.Context | None = None,
        ) -> list[dict]:
            """List all active (non-deleted) ingredients.

            Pass `name` for a partial, case-insensitive name filter.
            Each item: uuid, name, rayon, group, green_score, unit, quantity, season_months, created_at, updated_at, version.
            """
            await inject_tenant_uri(ctx)
            items = await service.find_by_name(name) if name else await service.find_all()
            logger.info("✅ Ingredients listed via MCP", count=len(items), filter=name)
            return [IngredientSchema.model_validate(i).model_dump() for i in items]

        @self._mcp.tool
        async def duplicate_ingredient(
                uuid: Annotated[str, Field(description="UUID (UUIDv7) of the ingredient to duplicate.",
                                           examples=["01951234-5678-7abc-def0-123456789abc"])],
                ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Duplicate an ingredient, assigning it a new UUID.

            Creates an independent copy with the same fields.
            Returns the new ingredient with its own UUID.
            """
            await inject_tenant_uri(ctx)
            result = await service.duplicate(to_uuid6(StdUUID(uuid)))
            logger.info("✅ Ingredient duplicated via MCP", source_uuid=uuid, new_uuid=str(result.uuid))
            return IngredientSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def list_recipes_for_ingredient(
                uuid: Annotated[str, Field(description="UUID (UUIDv7) of the ingredient.",
                                           examples=["01951234-5678-7abc-def0-123456789abc"])],
                ctx: fastmcp.Context | None = None,
        ) -> list[dict]:
            """List recipes using an ingredient."""
            await inject_tenant_uri(ctx)
            if recipe_service is None:
                raise RuntimeError("Recipe service is not available")
            items, _ = await recipe_service.find_page_filtered_hydrated(
                ingredient_uuid=to_uuid6(StdUUID(uuid)),
                offset=0,
                limit=None,
            )
            logger.info("✅ Ingredient recipes listed via MCP", uuid=uuid, count=len(items))
            return [RecipeSchema.model_validate(item).model_dump(mode="json") for item in items]

        @self._mcp.tool
        async def list_ingredient_duplicates(ctx: fastmcp.Context | None = None) -> list[dict]:
            """List ingredient duplicate groups detected by normalized name."""
            await inject_tenant_uri(ctx)
            groups = await service.find_duplicate_groups()
            logger.info("✅ Ingredient duplicates listed via MCP", count=len(groups))
            return [
                {
                    "normalized_name": group["normalized_name"],
                    "items": [{"uuid": str(item["uuid"]), "name": item["name"]} for item in group["items"]],
                }
                for group in groups
            ]

        @self._mcp.tool
        async def merge_ingredient_duplicates(
                target_uuid: Annotated[str, Field(description="Canonical ingredient UUID to keep.")],
                duplicate_uuids: Annotated[list[str], Field(description="Duplicate ingredient UUIDs to merge into the target.")],
                ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Merge ingredient duplicates into an explicit canonical target."""
            await require_auth_mcp(ctx)
            await inject_tenant_uri(ctx)
            if recipe_service is None:
                raise RuntimeError("Recipe service is not available")
            result = await service.merge_duplicates(
                to_uuid6(StdUUID(target_uuid)),
                [to_uuid6(StdUUID(uuid)) for uuid in duplicate_uuids],
                recipe_service,
            )
            logger.info(
                "✅ Ingredient duplicates merged via MCP",
                target_uuid=target_uuid,
                merged_count=len(result["merged_uuids"]),
            )
            return {
                "target_uuid": str(result["target_uuid"]),
                "merged_uuids": [str(uuid) for uuid in result["merged_uuids"]],
                "updated_recipe_count": result["updated_recipe_count"],
                "deleted_count": result["deleted_count"],
            }
