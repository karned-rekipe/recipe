from typing import Annotated
from uuid import UUID as StdUUID

import fastmcp
from pydantic import Field
from uuid6 import UUID

from adapters.input.fastmcp.authorization import DELETE_SCOPE, WRITE_SCOPE, secure_tool
from adapters.input.fastmcp.dependencies import inject_tenant_uri
from adapters.input.schemas.recipe_schema import RecipeSchema
from adapters.input.schemas.tag_schema import TagSchema
from application.services.recipe_service import RecipeService
from application.services.tag_service import TagService
from arclith.domain.ports.logger import Logger
from domain.models.tag import Tag, TagCategory


class TagMCP:
    def __init__(self, service: TagService, logger: Logger, mcp: fastmcp.FastMCP, recipe_service: RecipeService | None = None) -> None:
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
        async def create_tag(
            name: Annotated[str, Field(description="Tag name.", examples=["végan"])],
            category: Annotated[TagCategory, Field(description="Tag category.")] = TagCategory.other,
            color: Annotated[str | None, Field(default=None, description="Optional hex color.")] = None,
            ctx: fastmcp.Context | None = None,
        ) -> dict:
            await inject_tenant_uri(ctx)
            result = await service.create(Tag(name=name, category=category, color=color))
            logger.info("✅ Tag created via MCP", uuid=str(result.uuid), name=result.name)
            return TagSchema.model_validate(result).model_dump(mode="json")

        @secure_tool(self._mcp)
        async def list_tags(name: Annotated[str | None, Field(default=None, description="Optional partial name filter.")] = None, ctx: fastmcp.Context | None = None) -> list[dict]:
            await inject_tenant_uri(ctx)
            items = await service.find_by_name(name) if name else await service.find_all()
            return [TagSchema.model_validate(item).model_dump(mode="json") for item in items]

        @secure_tool(self._mcp)
        async def get_tag(uuid: Annotated[str, Field(description="Tag UUID.")], ctx: fastmcp.Context | None = None) -> dict | None:
            await inject_tenant_uri(ctx)
            result = await service.read(to_uuid6(StdUUID(uuid)))
            return TagSchema.model_validate(result).model_dump(mode="json") if result is not None else None

        @secure_tool(self._mcp, DELETE_SCOPE)
        async def delete_tag(uuid: Annotated[str, Field(description="Tag UUID.")], ctx: fastmcp.Context | None = None) -> None:
            await inject_tenant_uri(ctx)
            tag_uuid = to_uuid6(StdUUID(uuid))
            if recipe_service is not None and await recipe_service.is_tag_used(tag_uuid):
                raise ValueError("Tag is used by at least one recipe")
            await service.delete(tag_uuid)

        @secure_tool(self._mcp)
        async def list_recipes_for_tag(uuid: Annotated[str, Field(description="Tag UUID.")], ctx: fastmcp.Context | None = None) -> list[dict]:
            await inject_tenant_uri(ctx)
            if recipe_service is None:
                raise RuntimeError("Recipe service is not available")
            items, _ = await recipe_service.find_page_filtered_hydrated(tag_uuid=to_uuid6(StdUUID(uuid)), offset=0, limit=None)
            return [RecipeSchema.model_validate(item).model_dump(mode="json") for item in items]
