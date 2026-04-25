from typing import Annotated
from uuid import UUID as StdUUID

import fastmcp
from pydantic import Field
from uuid6 import UUID

from adapters.input.fastmcp.dependencies import inject_tenant_uri, require_auth_mcp
from adapters.input.schemas.ingredient_group_schema import IngredientGroupSchema
from adapters.input.schemas.ingredient_rayon_schema import IngredientRayonSchema
from application.services.ingredient_group_service import IngredientGroupService
from application.services.ingredient_rayon_service import IngredientRayonService
from application.services.ingredient_service import IngredientService
from arclith.domain.ports.logger import Logger
from domain.models.ingredient_group import IngredientGroup
from domain.models.ingredient_rayon import IngredientRayon


class IngredientGroupMCP:
    def __init__(self, service: IngredientGroupService, logger: Logger, mcp: fastmcp.FastMCP, ingredient_service: IngredientService | None = None) -> None:
        self._service = service
        self._logger = logger
        self._mcp = mcp
        self._ingredient_service = ingredient_service
        self._register_tools()

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    def _register_tools(self) -> None:
        service = self._service
        ingredient_service = self._ingredient_service
        to_uuid6 = self._to_uuid6

        @self._mcp.tool
        async def create_ingredient_group(name: Annotated[str, Field(description="Group name.")], ctx: fastmcp.Context | None = None) -> dict:
            await require_auth_mcp(ctx)
            await inject_tenant_uri(ctx)
            result = await service.create(IngredientGroup(name=name))
            return IngredientGroupSchema.model_validate(result).model_dump(mode="json")

        @self._mcp.tool
        async def list_ingredient_groups(name: Annotated[str | None, Field(default=None, description="Optional partial name filter.")] = None, ctx: fastmcp.Context | None = None) -> list[dict]:
            await inject_tenant_uri(ctx)
            items = await service.find_by_name(name) if name else await service.find_all()
            return [IngredientGroupSchema.model_validate(item).model_dump(mode="json") for item in items]

        @self._mcp.tool
        async def delete_ingredient_group(uuid: Annotated[str, Field(description="Group UUID.")], ctx: fastmcp.Context | None = None) -> None:
            await require_auth_mcp(ctx)
            await inject_tenant_uri(ctx)
            group_uuid = to_uuid6(StdUUID(uuid))
            if ingredient_service is not None and await ingredient_service.is_group_used(group_uuid):
                raise ValueError("Ingredient group is used by at least one ingredient")
            await service.delete(group_uuid)


class IngredientRayonMCP:
    def __init__(self, service: IngredientRayonService, logger: Logger, mcp: fastmcp.FastMCP, ingredient_service: IngredientService | None = None) -> None:
        self._service = service
        self._logger = logger
        self._mcp = mcp
        self._ingredient_service = ingredient_service
        self._register_tools()

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    def _register_tools(self) -> None:
        service = self._service
        ingredient_service = self._ingredient_service
        to_uuid6 = self._to_uuid6

        @self._mcp.tool
        async def create_ingredient_rayon(name: Annotated[str, Field(description="Rayon name.")], ctx: fastmcp.Context | None = None) -> dict:
            await require_auth_mcp(ctx)
            await inject_tenant_uri(ctx)
            result = await service.create(IngredientRayon(name=name))
            return IngredientRayonSchema.model_validate(result).model_dump(mode="json")

        @self._mcp.tool
        async def list_ingredient_rayons(name: Annotated[str | None, Field(default=None, description="Optional partial name filter.")] = None, ctx: fastmcp.Context | None = None) -> list[dict]:
            await inject_tenant_uri(ctx)
            items = await service.find_by_name(name) if name else await service.find_all()
            return [IngredientRayonSchema.model_validate(item).model_dump(mode="json") for item in items]

        @self._mcp.tool
        async def delete_ingredient_rayon(uuid: Annotated[str, Field(description="Rayon UUID.")], ctx: fastmcp.Context | None = None) -> None:
            await require_auth_mcp(ctx)
            await inject_tenant_uri(ctx)
            rayon_uuid = to_uuid6(StdUUID(uuid))
            if ingredient_service is not None and await ingredient_service.is_rayon_used(rayon_uuid):
                raise ValueError("Ingredient rayon is used by at least one ingredient")
            await service.delete(rayon_uuid)
