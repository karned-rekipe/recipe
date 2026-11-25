from typing import Annotated
from uuid import UUID as StdUUID

import fastmcp
from pydantic import Field
from uuid6 import UUID

from adapters.input.fastmcp.authorization import DELETE_SCOPE, IMAGE_GENERATE_SCOPE, WRITE_SCOPE, secure_tool
from adapters.input.fastmcp.dependencies import inject_tenant_uri
from adapters.input.schemas.equipment_schema import EquipmentSchema
from adapters.input.schemas.recipe_schema import RecipeSchema
from application.services.equipment_service import EquipmentService
from application.services.recipe_service import RecipeService
from arclith.domain.ports.logger import Logger
from domain.models.equipment import Equipment


class EquipmentMCP:
    def __init__(
        self,
        service: EquipmentService,
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

        @secure_tool(self._mcp, WRITE_SCOPE)
        async def create_equipment(
            name: Annotated[str, Field(description="Equipment name.", examples=["Four", "Saladier"])],
            description: Annotated[str | None, Field(default=None, description="Optional equipment details.")] = None,
            ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Create a new equipment item."""
            await inject_tenant_uri(ctx)
            result = await service.create(Equipment(name=name, description=description))
            logger.info("✅ Equipment created via MCP", uuid=str(result.uuid), name=result.name)
            return EquipmentSchema.model_validate(result).model_dump()

        @secure_tool(self._mcp)
        async def get_equipment(
            uuid: Annotated[str, Field(description="UUID (UUIDv7) of the equipment.",
                                       examples=["01951234-5678-7abc-def0-123456789abc"])],
            ctx: fastmcp.Context | None = None,
        ) -> dict | None:
            """Get equipment by UUID."""
            await inject_tenant_uri(ctx)
            result = await service.read(to_uuid6(StdUUID(uuid)))
            if result is None:
                logger.warning("⚠️ Equipment not found via MCP", uuid=uuid)
                return None
            logger.info("✅ Equipment fetched via MCP", uuid=uuid, name=result.name)
            return EquipmentSchema.model_validate(result).model_dump()

        @secure_tool(self._mcp, WRITE_SCOPE)
        async def update_equipment(
            uuid: Annotated[str, Field(description="UUID (UUIDv7) of the equipment.",
                                       examples=["01951234-5678-7abc-def0-123456789abc"])],
            name: Annotated[str, Field(description="New equipment name.", examples=["Four vapeur"])],
            description: Annotated[str | None, Field(default=None, description="Optional equipment details.")] = None,
            ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Replace equipment."""
            await inject_tenant_uri(ctx)
            existing = await service.read(to_uuid6(StdUUID(uuid)))
            if existing is None:
                raise KeyError(f"Equipment with uuid {uuid} not found")
            result = await service.update(Equipment(
                uuid=to_uuid6(StdUUID(uuid)),
                name=name,
                description=description,
                main_image=existing.main_image,
            ))
            logger.info("✅ Equipment updated via MCP", uuid=uuid, name=result.name)
            return EquipmentSchema.model_validate(result).model_dump()

        @secure_tool(self._mcp, IMAGE_GENERATE_SCOPE)
        async def generate_equipment_image(
            uuid: Annotated[
                str,
                Field(
                    description="UUID (UUIDv7) of the equipment whose main image must be generated.",
                    examples=["01951234-5678-7abc-def0-123456789abc"],
                ),
            ],
            replace_existing: Annotated[
                bool,
                Field(
                    default=False,
                    description="Allow replacement when the equipment already has a main image.",
                ),
            ] = False,
            ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Generate, store, and attach an equipment main image through media."""
            await inject_tenant_uri(ctx)
            equipment, generated = await service.generate_main_image(
                to_uuid6(StdUUID(uuid)),
                replace_existing=replace_existing,
            )
            logger.info(
                "✅ Equipment image generated via MCP",
                uuid=uuid,
                provider=generated.provider,
                image_url=generated.image.url,
            )
            return {
                "equipment": EquipmentSchema.model_validate(equipment).model_dump(mode="json"),
                **generated.model_dump(mode="json"),
            }

        @secure_tool(self._mcp, DELETE_SCOPE)
        async def delete_equipment(
            uuid: Annotated[str, Field(description="UUID (UUIDv7) of the equipment.",
                                       examples=["01951234-5678-7abc-def0-123456789abc"])],
            ctx: fastmcp.Context | None = None,
        ) -> None:
            """Soft-delete equipment if it is not used by a recipe."""
            await inject_tenant_uri(ctx)
            equipment_uuid = to_uuid6(StdUUID(uuid))
            if recipe_service is not None and await recipe_service.is_equipment_used(equipment_uuid):
                raise ValueError("Equipment is used by at least one recipe")
            await service.delete(equipment_uuid)
            logger.info("✅ Equipment deleted via MCP", uuid=uuid)

        @secure_tool(self._mcp)
        async def list_equipment(
            name: Annotated[str | None, Field(
                default=None,
                description="Optional partial name filter, case-insensitive.",
                examples=["four", None],
            )] = None,
            ctx: fastmcp.Context | None = None,
        ) -> list[dict]:
            """List active equipment."""
            await inject_tenant_uri(ctx)
            items = await service.find_by_name(name) if name else await service.find_all()
            logger.info("✅ Equipment listed via MCP", count=len(items), filter=name)
            return [EquipmentSchema.model_validate(item).model_dump() for item in items]

        @secure_tool(self._mcp, WRITE_SCOPE)
        async def duplicate_equipment(
            uuid: Annotated[str, Field(description="UUID (UUIDv7) of the equipment.",
                                       examples=["01951234-5678-7abc-def0-123456789abc"])],
            ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Duplicate equipment."""
            await inject_tenant_uri(ctx)
            result = await service.duplicate(to_uuid6(StdUUID(uuid)))
            logger.info("✅ Equipment duplicated via MCP", source_uuid=uuid, new_uuid=str(result.uuid))
            return EquipmentSchema.model_validate(result).model_dump()

        @secure_tool(self._mcp)
        async def list_recipes_for_equipment(
            uuid: Annotated[str, Field(description="UUID (UUIDv7) of the equipment.",
                                       examples=["01951234-5678-7abc-def0-123456789abc"])],
            ctx: fastmcp.Context | None = None,
        ) -> list[dict]:
            """List recipes using equipment."""
            await inject_tenant_uri(ctx)
            if recipe_service is None:
                raise RuntimeError("Recipe service is not available")
            items, _ = await recipe_service.find_page_filtered_hydrated(
                equipment_uuid=to_uuid6(StdUUID(uuid)),
                offset=0,
                limit=None,
            )
            logger.info("✅ Equipment recipes listed via MCP", uuid=uuid, count=len(items))
            return [RecipeSchema.model_validate(item).model_dump(mode="json") for item in items]

        @secure_tool(self._mcp)
        async def list_equipment_duplicates(ctx: fastmcp.Context | None = None) -> list[dict]:
            """List equipment duplicate groups detected by normalized name."""
            await inject_tenant_uri(ctx)
            groups = await service.find_duplicate_groups()
            logger.info("✅ Equipment duplicates listed via MCP", count=len(groups))
            return [
                {
                    "normalized_name": group["normalized_name"],
                    "items": [{"uuid": str(item["uuid"]), "name": item["name"]} for item in group["items"]],
                }
                for group in groups
            ]

        @secure_tool(self._mcp, WRITE_SCOPE)
        async def merge_equipment_duplicates(
            target_uuid: Annotated[str, Field(description="Canonical equipment UUID to keep.")],
            duplicate_uuids: Annotated[list[str], Field(description="Duplicate equipment UUIDs to merge into the target.")],
            ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Merge equipment duplicates into an explicit canonical target."""
            await inject_tenant_uri(ctx)
            if recipe_service is None:
                raise RuntimeError("Recipe service is not available")
            result = await service.merge_duplicates(
                to_uuid6(StdUUID(target_uuid)),
                [to_uuid6(StdUUID(uuid)) for uuid in duplicate_uuids],
                recipe_service,
            )
            logger.info(
                "✅ Equipment duplicates merged via MCP",
                target_uuid=target_uuid,
                merged_count=len(result["merged_uuids"]),
            )
            return {
                "target_uuid": str(result["target_uuid"]),
                "merged_uuids": [str(uuid) for uuid in result["merged_uuids"]],
                "updated_recipe_count": result["updated_recipe_count"],
                "deleted_count": result["deleted_count"],
            }
