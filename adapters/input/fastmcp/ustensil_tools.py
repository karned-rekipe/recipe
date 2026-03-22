from typing import Annotated
from uuid import UUID as StdUUID

import fastmcp
from arclith.domain.ports.logger import Logger
from pydantic import Field
from uuid6 import UUID

from adapters.input.fastmcp.dependencies import inject_tenant_uri
from adapters.input.schemas.ustensil_schema import UstensilSchema
from application.services.ustensil_service import UstensilService
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
                name: Annotated[str, Field(
                    description = "Nom de l'ustensile (ex. 'Fouet', 'Spatule', 'Casserole 20cm'). Sera normalisé (espaces rognés).",
                    examples = ["Fouet", "Spatule"])],
            ctx: fastmcp.Context = None,
        ) -> dict:
            """Create a new reusable ustensil.

            Returns the created ustensil with its generated UUID.
            Once created, use `link_ustensil_to_recipe` to attach it to a recipe.
            Fields returned: uuid, name, created_at, updated_at, version.
            """
            await inject_tenant_uri(ctx)
            result = await service.create(Ustensil(name=name))
            return UstensilSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def get_ustensil(
                uuid: Annotated[str, Field(description = "UUID (UUIDv7) de l'ustensile à récupérer.",
                                           examples = ["01951234-5678-7abc-def0-123456789abc"])],
            ctx: fastmcp.Context = None,
        ) -> dict | None:
            """Get an ustensil by its UUID.

            Returns the full ustensil object or null if not found.
            Fields: uuid, name, created_at, updated_at, version.
            """
            await inject_tenant_uri(ctx)
            result = await service.read(to_uuid6(StdUUID(uuid)))
            if result is None:
                logger.warning("⚠️ Ustensil not found via MCP", uuid=uuid)
                return None
            return UstensilSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def update_ustensil(
                uuid: Annotated[str, Field(description = "UUID (UUIDv7) de l'ustensile à modifier.",
                                           examples = ["01951234-5678-7abc-def0-123456789abc"])],
                name: Annotated[str, Field(description = "Nouveau nom de l'ustensile.",
                                           examples = ["Fouet électrique", "Grande spatule"])],
            ctx: fastmcp.Context = None,
        ) -> dict:
            """Replace the name of an existing ustensil.

            Returns the updated ustensil.
            Note: updating an ustensil does not propagate to recipes where it is already linked (snapshot model).
            """
            await inject_tenant_uri(ctx)
            result = await service.update(Ustensil(uuid=to_uuid6(StdUUID(uuid)), name=name))
            return UstensilSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def delete_ustensil(
                uuid: Annotated[str, Field(description = "UUID (UUIDv7) de l'ustensile à supprimer.",
                                           examples = ["01951234-5678-7abc-def0-123456789abc"])],
            ctx: fastmcp.Context = None,
        ) -> None:
            """Soft-delete an ustensil.

            The ustensil is marked as deleted and excluded from list results.
            It is retained until the purge retention period expires.
            Use `purge_ustensils` to permanently remove expired entries.
            """
            await inject_tenant_uri(ctx)
            await service.delete(to_uuid6(StdUUID(uuid)))

        @self._mcp.tool
        async def list_ustensils(
                name: Annotated[str | None, Field(default = None,
                                                  description = "Filtre optionnel : recherche partielle sur le nom, insensible à la casse. Ex: 'fou' retournera 'Fouet'.",
                                                  examples = ["fouet", None])] = None,
            ctx: fastmcp.Context = None,
        ) -> list[dict]:
            """List all active (non-deleted) ustensils.

            Pass `name` for a partial, case-insensitive name filter.
            Each item: uuid, name, created_at, updated_at, version.
            Use these UUIDs with `link_ustensil_to_recipe` to attach ustensils to a recipe.
            """
            await inject_tenant_uri(ctx)
            items = await service.find_by_name(name) if name else await service.find_all()
            return [UstensilSchema.model_validate(i).model_dump() for i in items]

        @self._mcp.tool
        async def duplicate_ustensil(
                uuid: Annotated[str, Field(description = "UUID (UUIDv7) de l'ustensile à dupliquer.",
                                           examples = ["01951234-5678-7abc-def0-123456789abc"])],
            ctx: fastmcp.Context = None,
        ) -> dict:
            """Duplicate an ustensil, assigning it a new UUID.

            Creates an independent copy with the same name.
            Returns the new ustensil with its own UUID.
            """
            await inject_tenant_uri(ctx)
            result = await service.duplicate(to_uuid6(StdUUID(uuid)))
            return UstensilSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def purge_ustensils(ctx: fastmcp.Context = None) -> dict:
            """Permanently delete soft-deleted ustensils that have exceeded the retention period.

            Returns {"purged": <count>} with the number of permanently deleted records.
            This operation is irreversible.
            """
            await inject_tenant_uri(ctx)
            purged = await service.purge()
            return {"purged": purged}
