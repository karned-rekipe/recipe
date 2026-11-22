import fastmcp

from adapters.input.fastmcp.authorization import secure_prompt
from adapters.input.fastmcp.dependencies import inject_tenant_uri
from application.services.recipe_service import RecipeService
from arclith.domain.ports.logger import Logger

_EXPLORE_PREVIEW_LIMIT = 20


class RecipePrompts:
    def __init__(self, service: RecipeService, logger: Logger, mcp: fastmcp.FastMCP) -> None:
        self._service = service
        self._logger = logger
        self._mcp = mcp
        self._register_prompts()

    def _register_prompts(self) -> None:
        service = self._service

        @secure_prompt(self._mcp)
        def check_duplicate(recipe_name: str) -> str:
            """Check for duplicates before creating a new recipe.

            Use this prompt before calling create_recipe.
            The LLM will guide you to call list_recipes with a partial
            name filter to surface any existing match.
            """
            return (
                f"Before creating the recipe '{recipe_name}', "
                "call list_recipes with a partial name filter to check for existing similar entries. "
                "If a match is found, suggest using the existing one instead of creating a duplicate."
            )

        @secure_prompt(self._mcp)
        async def explore_recipes(ctx: fastmcp.Context) -> str:
            """Explore and discover available recipes.

            Loads the current catalog and guides the LLM to help the user
            search by name or identify what is available.
            """
            await inject_tenant_uri(ctx)
            items = await service.find_all()
            if not items:
                snapshot = "No recipes available yet. Use create_recipe to add the first one."
            else:
                names = ", ".join(i.name for i in items[:_EXPLORE_PREVIEW_LIMIT])
                total = len(items)
                snapshot = f"{total} recipe(s) available: {names}{'...' if total > _EXPLORE_PREVIEW_LIMIT else '.'}"
            return (
                f"{snapshot}\n\n"
                "Help me explore these recipes: search by name, "
                "or suggest which ones to use for a given dish."
            )

        @secure_prompt(self._mcp)
        def mcp_help() -> str:
            """Overview of all MCP capabilities exposed by this server.

            Lists every tool, prompt, and resource with a short description.
            Use this as a starting point when discovering what this server can do.
            """
            return (
                "Here are all the capabilities exposed by this MCP server:\n\n"
                "**Tools** (actions):\n"
                "- create_recipe(payload) — create a complete recipe aggregate\n"
                "- get_recipe(uuid) — retrieve by UUID\n"
                "- update_recipe(uuid, payload) — full replacement (PUT semantics)\n"
                "- patch_recipe(uuid, payload) — partial update (PATCH semantics)\n"
                "- delete_recipe(uuid) — soft-delete\n"
                "- list_recipes(filters...) — list non-deleted recipes; use "
                "has_main_image=false to find recipes that need an image\n"
                "- duplicate_recipe(uuid) — clone with a new UUID\n"
                "- generate_recipe_image(uuid) — generate and attach the main image\n"
                "- ai_enrich_recipe(uuid, generate_image) — enrich and reorganize an existing recipe via the internal AI agent\n"
                "- purge_recipes() — permanently remove expired soft-deleted entries\n\n"
                "**Prompts** (LLM guidance):\n"
                "- check_duplicate(recipe_name) — avoid duplicates before creating\n"
                "- explore_recipes — discover and filter available recipes\n"
                "- mcp_help — this overview\n\n"
                "**Resources** (read-only data):\n"
                "- recipes://sample — first 5 recipes (quick dataset preview)\n"
                "- recipes://recent — last 10 recipes by creation date, newest first\n"
                "- recipe://{uuid} — single recipe by UUID\n"
            )
