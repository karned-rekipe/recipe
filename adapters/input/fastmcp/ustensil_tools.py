from typing import Annotated
from uuid import UUID as StdUUID
from uuid6 import UUID

import fastmcp
from pydantic import Field

from adapters.input.fastmcp.dependencies import inject_tenant_uri
from adapters.input.schemas.ustensil_schema import UstensilSchema
from application.services.ustensil_service import UstensilService
from arclith.domain.ports.logger import Logger
from domain.models.ustensil import Ustensil


class UstensilMCP:
    def __init__(self, service: UstensilService, logger: Logger, mcp: fastmcp.FastMCP) -> None:
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
        async def create_ustensil(
            name: Annotated[str, Field(description="Nom de l'ustensil.", examples=["Fouet", "Spatule"])],
            ctx: fastmcp.Context = None,
        ) -> dict:
            """Create a new ustensil."""
            await inject_tenant_uri(ctx)
            result = await service.create(Ustensil(name=name))
            return UstensilSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def get_ustensil(
            uuid: Annotated[str, Field(description="UUID de l'ustensil.", examples=["01951234-5678-7abc-def0-123456789abc"])],
            ctx: fastmcp.Context = None,
        ) -> dict | None:
            """Get an ustensil by its UUID."""
            await inject_tenant_uri(ctx)
            result = await service.read(to_uuid6(StdUUID(uuid)))
            if result is None:
                logger.warning("⚠️ Ustensil not found via MCP", uuid=uuid)
                return None
            return UstensilSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def update_ustensil(
            uuid: Annotated[str, Field(description="UUID de l'ustensil à modifier.", examples=["01951234-5678-7abc-def0-123456789abc"])],
            name: Annotated[str, Field(description="Nouveau nom de l'ustensil.", examples=["Fouet électrique"])],
            ctx: fastmcp.Context = None,
        ) -> dict:
            """Update an existing ustensil."""
            await inject_tenant_uri(ctx)
            result = await service.update(Ustensil(uuid=to_uuid6(StdUUID(uuid)), name=name))
            return UstensilSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def delete_ustensil(
            uuid: Annotated[str, Field(description="UUID de l'ustensil à supprimer.", examples=["01951234-5678-7abc-def0-123456789abc"])],
            ctx: fastmcp.Context = None,
        ) -> None:
            """Delete an ustensil by its UUID."""
            await inject_tenant_uri(ctx)
            await service.delete(to_uuid6(StdUUID(uuid)))

        @self._mcp.tool
        async def list_ustensils(
            name: Annotated[str | None, Field(default=None, description="Filtre par nom (recherche partielle, insensible à la casse).", examples=["fouet", None])] = None,
            ctx: fastmcp.Context = None,
        ) -> list[dict]:
            """List all ustensils, optionally filtered by name."""
            await inject_tenant_uri(ctx)
            items = await service.find_by_name(name) if name else await service.find_all()
            return [UstensilSchema.model_validate(i).model_dump() for i in items]

        @self._mcp.tool
        async def duplicate_ustensil(
            uuid: Annotated[str, Field(description="UUID de l'ustensil à dupliquer.", examples=["01951234-5678-7abc-def0-123456789abc"])],
            ctx: fastmcp.Context = None,
        ) -> dict:
            """Duplicate an ustensil, assigning it a new UUID."""
            await inject_tenant_uri(ctx)
            result = await service.duplicate(to_uuid6(StdUUID(uuid)))
            return UstensilSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def purge_ustensils(ctx: fastmcp.Context = None) -> dict:
            """Purge all soft-deleted ustensils that have exceeded the retention period."""
            await inject_tenant_uri(ctx)
            purged = await service.purge()
            return {"purged": purged}
