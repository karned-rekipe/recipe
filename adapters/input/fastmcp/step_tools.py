from typing import Annotated
from uuid import UUID as StdUUID
from uuid6 import UUID

import fastmcp
from pydantic import Field

from adapters.input.fastmcp.dependencies import inject_tenant_uri
from adapters.input.schemas.step_schema import StepSchema
from application.services.step_service import StepService
from arclith.domain.ports.logger import Logger
from domain.models.step import Step


class StepMCP:
    def __init__(self, service: StepService, logger: Logger, mcp: fastmcp.FastMCP) -> None:
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
        async def create_step(
            name: Annotated[str, Field(description="Nom de la recette.", examples=["Pizza Margherita", "Salade niçoise"])],
            description: Annotated[str | None, Field(default=None, description="Description de la recette.", examples=["Une pizza classique italienne.", None])] = None,
            ctx: fastmcp.Context = None,
        ) -> dict:
            """Create a new step."""
            await inject_tenant_uri(ctx)
            result = await service.create(Step(name=name, description=description))
            return StepSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def get_step(
            uuid: Annotated[str, Field(description="UUID de la recette.", examples=["01951234-5678-7abc-def0-123456789abc"])],
            ctx: fastmcp.Context = None,
        ) -> dict | None:
            """Get a step by its UUID."""
            await inject_tenant_uri(ctx)
            result = await service.read(to_uuid6(StdUUID(uuid)))
            if result is None:
                logger.warning("⚠️ Step not found via MCP", uuid=uuid)
                return None
            return StepSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def update_step(
            uuid: Annotated[str, Field(description="UUID de la recette à modifier.", examples=["01951234-5678-7abc-def0-123456789abc"])],
            name: Annotated[str, Field(description="Nouveau nom de la recette.", examples=["Pizza Margherita"])],
            description: Annotated[str | None, Field(default=None, description="Nouvelle description.", examples=["Une pizza classique italienne.", None])] = None,
            ctx: fastmcp.Context = None,
        ) -> dict:
            """Update an existing step."""
            await inject_tenant_uri(ctx)
            result = await service.update(Step(uuid=to_uuid6(StdUUID(uuid)), name=name, description=description))
            return StepSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def delete_step(
            uuid: Annotated[str, Field(description="UUID de la recette à supprimer.", examples=["01951234-5678-7abc-def0-123456789abc"])],
            ctx: fastmcp.Context = None,
        ) -> None:
            """Delete a step by its UUID."""
            await inject_tenant_uri(ctx)
            await service.delete(to_uuid6(StdUUID(uuid)))

        @self._mcp.tool
        async def list_steps(
            name: Annotated[str | None, Field(default=None, description="Filtre par nom (recherche partielle, insensible à la casse).", examples=["pizza", None])] = None,
            ctx: fastmcp.Context = None,
        ) -> list[dict]:
            """List all steps, optionally filtered by name."""
            await inject_tenant_uri(ctx)
            items = await service.find_by_name(name) if name else await service.find_all()
            return [StepSchema.model_validate(i).model_dump() for i in items]

        @self._mcp.tool
        async def duplicate_step(
            uuid: Annotated[str, Field(description="UUID de la recette à dupliquer.", examples=["01951234-5678-7abc-def0-123456789abc"])],
            ctx: fastmcp.Context = None,
        ) -> dict:
            """Duplicate a step, assigning it a new UUID."""
            await inject_tenant_uri(ctx)
            result = await service.duplicate(to_uuid6(StdUUID(uuid)))
            return StepSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def purge_steps(ctx: fastmcp.Context = None) -> dict:
            """Purge all soft-deleted steps that have exceeded the retention period."""
            await inject_tenant_uri(ctx)
            purged = await service.purge()
            return {"purged": purged}
