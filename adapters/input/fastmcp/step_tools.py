from typing import Annotated
from uuid import UUID as StdUUID

import fastmcp
from arclith.domain.ports.logger import Logger
from pydantic import Field
from uuid6 import UUID

from adapters.input.fastmcp.dependencies import inject_tenant_uri
from adapters.input.schemas.step_schema import StepSchema
from application.services.step_service import StepService
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
                recipe_uuid: Annotated[
                    str, Field(description = "UUID (UUIDv7) de la recette à laquelle appartient cette étape.",
                               examples = ["01951234-5678-7abc-def0-123456789abc"])],
                name: Annotated[str, Field(
                    description = "Nom court de l'étape (max 80 caractères), ex. 'Préparer la pâte', 'Cuire au four'.",
                    examples = ["Préparer la pâte", "Cuire la pizza"])],
                description: Annotated[str | None, Field(default = None,
                                                         description = "Description détaillée des actions à effectuer pour cette étape.",
                                                         examples = [
                                                             "Mélanger la farine, l'eau et la levure pendant 10 min.",
                                                             None])] = None,
            ctx: fastmcp.Context = None,
        ) -> dict:
            """Create a new step linked to a recipe.

            Steps define the preparation procedure of a recipe in chronological order.
            Returns the created step with its UUID.
            Fields returned: uuid, recipe_uuid, name, description, created_at, updated_at, version.
            Use `list_steps_for_recipe` to retrieve all steps of a recipe.
            """
            await inject_tenant_uri(ctx)
            result = await service.create(
                Step(recipe_uuid = to_uuid6(StdUUID(recipe_uuid)), name = name, description = description))
            return StepSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def get_step(
                uuid: Annotated[str, Field(description = "UUID (UUIDv7) de l'étape à récupérer.",
                                           examples = ["01951234-5678-7abc-def0-123456789abc"])],
            ctx: fastmcp.Context = None,
        ) -> dict | None:
            """Get a step by its UUID.

            Returns the full step object or null if not found.
            Fields: uuid, recipe_uuid, name, description, created_at, updated_at, version.
            """
            await inject_tenant_uri(ctx)
            result = await service.read(to_uuid6(StdUUID(uuid)))
            if result is None:
                logger.warning("⚠️ Step not found via MCP", uuid=uuid)
                return None
            return StepSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def update_step(
                uuid: Annotated[str, Field(description = "UUID (UUIDv7) de l'étape à modifier.",
                                           examples = ["01951234-5678-7abc-def0-123456789abc"])],
                name: Annotated[str, Field(description = "Nouveau nom de l'étape (max 80 caractères).",
                                           examples = ["Préparer la pâte", "Préchauffer le four"])],
                description: Annotated[str | None, Field(default = None,
                                                         description = "Nouvelle description détaillée. Passer null pour la supprimer.",
                                                         examples = ["Mélanger la farine et l'eau.", None])] = None,
            ctx: fastmcp.Context = None,
        ) -> dict | None:
            """Update name and description of an existing step.

            Reads the existing step first to preserve its recipe_uuid.
            Returns the updated step, or null if the step was not found.
            """
            await inject_tenant_uri(ctx)
            existing = await service.read(to_uuid6(StdUUID(uuid)))
            if existing is None:
                logger.warning("⚠️ Step not found via MCP", uuid = uuid)
                return None
            result = await service.update(
                Step(uuid = existing.uuid, recipe_uuid = existing.recipe_uuid, name = name, description = description))
            return StepSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def delete_step(
                uuid: Annotated[str, Field(description = "UUID (UUIDv7) de l'étape à supprimer.",
                                           examples = ["01951234-5678-7abc-def0-123456789abc"])],
            ctx: fastmcp.Context = None,
        ) -> None:
            """Soft-delete a step.

            The step is marked as deleted and excluded from list results.
            Use `purge_steps` to permanently remove expired entries.
            """
            await inject_tenant_uri(ctx)
            await service.delete(to_uuid6(StdUUID(uuid)))

        @self._mcp.tool
        async def list_steps(
                name: Annotated[str | None, Field(default = None,
                                                  description = "Filtre optionnel : recherche partielle sur le nom, insensible à la casse.",
                                                  examples = ["pâte", None])] = None,
            ctx: fastmcp.Context = None,
        ) -> list[dict]:
            """List all active steps across all recipes, optionally filtered by name.

            Prefer `list_steps_for_recipe` when you want the steps of a specific recipe.
            Each item: uuid, recipe_uuid, name, description, created_at, updated_at, version.
            """
            await inject_tenant_uri(ctx)
            items = await service.find_by_name(name) if name else await service.find_all()
            return [StepSchema.model_validate(i).model_dump() for i in items]

        @self._mcp.tool
        async def duplicate_step(
                uuid: Annotated[str, Field(description = "UUID (UUIDv7) de l'étape à dupliquer.",
                                           examples = ["01951234-5678-7abc-def0-123456789abc"])],
            ctx: fastmcp.Context = None,
        ) -> dict:
            """Duplicate a step, assigning it a new UUID.

            The copy remains linked to the same recipe.
            Returns the new step with its own UUID.
            """
            await inject_tenant_uri(ctx)
            result = await service.duplicate(to_uuid6(StdUUID(uuid)))
            return StepSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def list_steps_for_recipe(
                recipe_uuid: Annotated[
                    str, Field(description = "UUID (UUIDv7) de la recette dont on veut récupérer les étapes.",
                               examples = ["01951234-5678-7abc-def0-123456789abc"])],
                ctx: fastmcp.Context = None,
        ) -> list[dict]:
            """List all steps belonging to a specific recipe.

            Returns steps in creation order (UUIDv7 time-ordered).
            Each item: uuid, recipe_uuid, name, description, created_at, updated_at, version.
            """
            await inject_tenant_uri(ctx)
            items = await service.find_by_recipe(to_uuid6(StdUUID(recipe_uuid)))
            return [StepSchema.model_validate(i).model_dump() for i in items]

        @self._mcp.tool
        async def purge_steps(ctx: fastmcp.Context = None) -> dict:
            """Permanently delete soft-deleted steps that have exceeded the retention period.

            Returns {"purged": <count>} with the number of permanently deleted records.
            This operation is irreversible.
            """
            await inject_tenant_uri(ctx)
            purged = await service.purge()
            return {"purged": purged}
