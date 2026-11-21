import fastmcp

from adapters.input.fastmcp.authorization import ADMIN_SCOPE, secure_tool
from arclith.domain.ports.logger import Logger
from infrastructure.purge_registry import PurgeRegistry


class AdminMCP:
    def __init__(self, registry: PurgeRegistry, logger: Logger, mcp: fastmcp.FastMCP) -> None:
        self._registry = registry
        self._logger = logger
        self._register_tools(mcp)

    def _register_tools(self, mcp: fastmcp.FastMCP) -> None:
        registry = self._registry
        logger = self._logger

        @secure_tool(mcp, ADMIN_SCOPE)
        async def purge_all(ctx: fastmcp.Context | None = None) -> dict:
            """Permanently delete all soft-deleted entities across all collections.

            Runs all registered entity purges in parallel.
            Returns {"purged": {"recipes": N, ...}, "total": N}.
            This operation is irreversible.
            """
            results = await registry.purge_all()
            total = sum(results.values())
            logger.info("✅ Global purge via MCP", total=total, breakdown=results)
            return {"purged": results, "total": total}
