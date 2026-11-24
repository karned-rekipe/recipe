import fastmcp
from pydantic import Field
from uuid6 import UUID

from adapters.input.fastmcp.authorization import DELETE_SCOPE, IMAGE_GENERATE_SCOPE, WRITE_SCOPE, secure_tool
from adapters.input.fastmcp.dependencies import inject_tenant_uri
from adapters.input.schemas.ingredient_enrichment_suggestion_schema import IngredientEnrichmentSuggestionSchema
from adapters.input.schemas.ingredient_schema import IngredientSchema
from adapters.input.schemas.recipe_schema import RecipeSchema
from application.services.ingredient_enrichment_suggestion_service import IngredientEnrichmentSuggestionService
from application.services.ingredient_service import IngredientService
from application.services.recipe_service import RecipeService
from arclith.domain.ports.logger import Logger
from domain.models.ingredient import Ingredient
from domain.models.ingredient_enrichment_suggestion import IngredientEnrichmentSuggestion
from typing import Annotated
from uuid import UUID as StdUUID


class IngredientMCP:
    def __init__(
            self,
            service: IngredientService,
            logger: Logger,
            mcp: fastmcp.FastMCP,
            recipe_service: RecipeService | None = None,
            suggestion_service: IngredientEnrichmentSuggestionService | None = None,
    ) -> None:
        self._service = service
        self._logger = logger
        self._mcp = mcp
        self._recipe_service = recipe_service
        self._suggestion_service = suggestion_service
        self._register_tools()

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    def _register_tools(self) -> None:
        service = self._service
        logger = self._logger
        recipe_service = self._recipe_service
        suggestion_service = self._suggestion_service
        to_uuid6 = self._to_uuid6

        async def hydrate_ingredients_with_media_previews(items: list[Ingredient]) -> list[dict]:
            items_without_image = [
                item
                for item in items
                if not item.media_profile.main_image_uri or not item.media_profile.main_image_uri.strip()
            ]
            suggested_media_profiles = (
                await suggestion_service.find_suggested_media_profiles([item.uuid for item in items_without_image])
                if suggestion_service is not None and items_without_image
                else {}
            )
            return await service.hydrate_ingredients(items, suggested_media_profiles)

        @secure_tool(self._mcp, WRITE_SCOPE)
        async def create_ingredient(
                name: Annotated[str, Field(
                    description="Ingredient name (e.g. 'Tomate', 'Farine de blé'). Will be normalized (spaces trimmed).",
                    examples=["Tomate", "Farine de blé"])],
                rayon_uuid: Annotated[str | None, Field(default=None, description="Shelf/aisle UUID.")] = None,
                group_uuid: Annotated[str | None, Field(default=None, description="Food group UUID.")] = None,
                main_supplier_uuid: Annotated[str | None, Field(default=None, description="Preferred supplier UUID.")] = None,
                secondary_supplier_uuids: Annotated[list[str] | None, Field(default=None, description="Other possible supplier UUIDs.")] = None,
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
            await inject_tenant_uri(ctx)
            result = await service.create(Ingredient(
                name=name,
                rayon_uuid=to_uuid6(StdUUID(rayon_uuid)) if rayon_uuid else None,
                group_uuid=to_uuid6(StdUUID(group_uuid)) if group_uuid else None,
                main_supplier_uuid=to_uuid6(StdUUID(main_supplier_uuid)) if main_supplier_uuid else None,
                secondary_supplier_uuids=[to_uuid6(StdUUID(uuid)) for uuid in secondary_supplier_uuids or []],
                green_score=green_score,
                unit=unit,
                quantity=quantity,
                season_months=season_months,
            ))
            logger.info("✅ Ingredient created via MCP", uuid=str(result.uuid), name=result.name)
            return IngredientSchema.model_validate(result).model_dump()

        @secure_tool(self._mcp)
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
            hydrated = (await hydrate_ingredients_with_media_previews([result]))[0]
            return IngredientSchema.model_validate(hydrated).model_dump()

        @secure_tool(self._mcp, WRITE_SCOPE)
        async def update_ingredient(
                uuid: Annotated[str, Field(description="UUID (UUIDv7) of the ingredient to update.",
                                           examples=["01951234-5678-7abc-def0-123456789abc"])],
                name: Annotated[str, Field(description="New ingredient name.", examples=["Farine complète"])],
                rayon_uuid: Annotated[str | None, Field(default=None, description="Shelf/aisle UUID.")] = None,
                group_uuid: Annotated[str | None, Field(default=None, description="Food group UUID.")] = None,
                main_supplier_uuid: Annotated[str | None, Field(default=None, description="Preferred supplier UUID.")] = None,
                secondary_supplier_uuids: Annotated[list[str] | None, Field(default=None, description="Other possible supplier UUIDs.")] = None,
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
                main_supplier_uuid=to_uuid6(StdUUID(main_supplier_uuid)) if main_supplier_uuid else None,
                secondary_supplier_uuids=[to_uuid6(StdUUID(supplier_uuid)) for supplier_uuid in secondary_supplier_uuids or []],
                green_score=green_score,
                unit=unit,
                quantity=quantity,
                season_months=season_months,
            ))
            logger.info("✅ Ingredient updated via MCP", uuid=uuid, name=result.name)
            return IngredientSchema.model_validate(result).model_dump()

        @secure_tool(self._mcp, DELETE_SCOPE)
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
            await inject_tenant_uri(ctx)
            ingredient_uuid = to_uuid6(StdUUID(uuid))
            if recipe_service is not None and await recipe_service.is_ingredient_used(ingredient_uuid):
                raise ValueError("Ingredient is used by at least one recipe")
            await service.delete(ingredient_uuid)
            logger.info("✅ Ingredient deleted via MCP", uuid=uuid)

        @secure_tool(self._mcp)
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
            hydrated = await hydrate_ingredients_with_media_previews(items)
            return [IngredientSchema.model_validate(item).model_dump() for item in hydrated]

        @secure_tool(self._mcp)
        async def list_units(ctx: fastmcp.Context | None = None) -> list[dict]:
            """List reusable ingredient units and their categories."""
            await inject_tenant_uri(ctx)
            return await service.list_units()

        @secure_tool(self._mcp, IMAGE_GENERATE_SCOPE)
        async def generate_ingredient_image(
                uuid: Annotated[
                    str,
                    Field(
                        description="UUID (UUIDv7) of the ingredient requiring an image suggestion.",
                        examples=["01951234-5678-7abc-def0-123456789abc"],
                    ),
                ],
                ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Generate one constrained ingredient image and create a reviewable suggestion."""
            await inject_tenant_uri(ctx)
            result = await service.generate_main_image_suggestion(
                to_uuid6(StdUUID(uuid))
            )
            logger.info(
                "✅ Ingredient image suggestion generated via MCP",
                uuid=uuid,
                run_uuid=result.run_uuid,
                suggestion_uuid=result.suggestion_uuid,
            )
            return result.model_dump(mode="json")

        @secure_tool(self._mcp)
        async def convert_ingredient_unit(
                ingredient_uuid: Annotated[str, Field(description="Ingredient UUID.")],
                quantity: Annotated[float, Field(description="Quantity to convert.", gt=0)],
                from_unit: Annotated[str, Field(description="Source unit code.")],
                to_unit: Annotated[str, Field(description="Target unit code.")],
                ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Convert an ingredient quantity using global or ingredient-specific conversions."""
            await inject_tenant_uri(ctx)
            result = await service.convert_unit(
                to_uuid6(StdUUID(ingredient_uuid)),
                quantity,
                from_unit,
                to_unit,
            )
            return {
                "ingredient_uuid": str(result["ingredient_uuid"]),
                "quantity": result["quantity"],
                "from_unit": result["from_unit"],
                "converted_quantity": result["converted_quantity"],
                "to_unit": result["to_unit"],
                "factor": result["factor"],
                "source": result["source"],
            }

        @secure_tool(self._mcp, WRITE_SCOPE)
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

        @secure_tool(self._mcp)
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

        @secure_tool(self._mcp)
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

        @secure_tool(self._mcp, WRITE_SCOPE)
        async def merge_ingredient_duplicates(
                target_uuid: Annotated[str, Field(description="Canonical ingredient UUID to keep.")],
                duplicate_uuids: Annotated[list[str], Field(description="Duplicate ingredient UUIDs to merge into the target.")],
                ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Merge ingredient duplicates into an explicit canonical target."""
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

        @secure_tool(self._mcp, WRITE_SCOPE)
        async def create_ingredient_enrichment_suggestion(
                ingredient_uuid: Annotated[str, Field(description="Ingredient UUID targeted by the suggestion.")],
                run_uuid: Annotated[str, Field(description="Agent run UUID that produced the suggestion.")],
                proposed_patch: Annotated[dict, Field(description="Top-level Ingredient V5 patch to propose.")],
                field_confidences: Annotated[dict[str, float] | None, Field(default=None)] = None,
                field_sources: Annotated[dict[str, str] | None, Field(default=None)] = None,
                reasoning_summary: Annotated[str, Field(default="", description="Short explanation for humans.")] = "",
                ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Create a V5 enrichment suggestion for an ingredient."""
            await inject_tenant_uri(ctx)
            if suggestion_service is None:
                raise RuntimeError("Ingredient enrichment suggestion service is not available")
            suggestion = await suggestion_service.create(
                IngredientEnrichmentSuggestion(
                    ingredient_uuid=to_uuid6(StdUUID(ingredient_uuid)),
                    run_uuid=to_uuid6(StdUUID(run_uuid)),
                    proposed_patch=proposed_patch,
                    field_confidences=field_confidences or {},
                    field_sources=field_sources or {},
                    reasoning_summary=reasoning_summary,
                )
            )
            return {"uuid": str(suggestion.uuid)}

        @secure_tool(self._mcp)
        async def list_ingredient_enrichment_suggestions(
                ingredient_uuid: Annotated[str, Field(description="Ingredient UUID.")],
                ctx: fastmcp.Context | None = None,
        ) -> list[dict]:
            """List V5 enrichment suggestions for an ingredient."""
            await inject_tenant_uri(ctx)
            if suggestion_service is None:
                raise RuntimeError("Ingredient enrichment suggestion service is not available")
            suggestions = await suggestion_service.find_by_ingredient_uuid(to_uuid6(StdUUID(ingredient_uuid)))
            return [IngredientEnrichmentSuggestionSchema.model_validate(item).model_dump(mode="json") for item in suggestions]

        @secure_tool(self._mcp, WRITE_SCOPE)
        async def apply_ingredient_enrichment_suggestion(
                ingredient_uuid: Annotated[str, Field(description="Ingredient UUID.")],
                suggestion_uuid: Annotated[str, Field(description="Suggestion UUID.")],
                fields: Annotated[list[str] | None, Field(default=None, description="Optional top-level fields to apply.")] = None,
                force: Annotated[bool, Field(default=False, description="Allow overwriting validated fields.")] = False,
                ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Apply selected fields from a V5 enrichment suggestion."""
            await inject_tenant_uri(ctx)
            if suggestion_service is None:
                raise RuntimeError("Ingredient enrichment suggestion service is not available")
            suggestion = await suggestion_service.apply(
                to_uuid6(StdUUID(ingredient_uuid)),
                to_uuid6(StdUUID(suggestion_uuid)),
                fields=fields,
                force=force,
            )
            return IngredientEnrichmentSuggestionSchema.model_validate(suggestion).model_dump(mode="json")

        @secure_tool(self._mcp, WRITE_SCOPE)
        async def reject_ingredient_enrichment_suggestion(
                ingredient_uuid: Annotated[str, Field(description="Ingredient UUID.")],
                suggestion_uuid: Annotated[str, Field(description="Suggestion UUID.")],
                fields: Annotated[list[str] | None, Field(default=None, description="Optional top-level fields to reject.")] = None,
                ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Reject a V5 enrichment suggestion."""
            await inject_tenant_uri(ctx)
            if suggestion_service is None:
                raise RuntimeError("Ingredient enrichment suggestion service is not available")
            suggestion = await suggestion_service.reject(
                to_uuid6(StdUUID(ingredient_uuid)),
                to_uuid6(StdUUID(suggestion_uuid)),
                fields=fields,
            )
            return IngredientEnrichmentSuggestionSchema.model_validate(suggestion).model_dump(mode="json")
