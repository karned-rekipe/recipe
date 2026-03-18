from arclith import Logger
from fastapi import APIRouter, Depends, HTTPException
from uuid6 import UUID
from uuid import UUID as StdUUID

from adapters.input.fastapi.dependencies import inject_tenant_uri
from adapters.input.schemas.tool_schema import ToolSchema, ToolCreateSchema, ToolCreatedSchema
from application.services.tool_service import ToolService
from domain.models.tool import Tool


class ToolRouter:
    def __init__(self, service: ToolService, logger: Logger) -> None:
        self._service = service
        self._logger = logger
        self.router = APIRouter(
            prefix="/v1/tools",
            tags=["tools"],
            dependencies=[Depends(inject_tenant_uri)]
        )
        self._register_routes()


    def _register_routes(self) -> None:
        self.router.add_api_route("/", self.create_tool, methods=["POST"], response_model=ToolCreatedSchema, status_code=201)
        self.router.add_api_route("/", self.list_tools, methods=["GET"], response_model=list[ToolSchema], status_code=200)
        self.router.add_api_route("/{name}", self.find_tools_by_name, methods=["GET"], response_model=list[ToolSchema], status_code=200)
        self.router.add_api_route("/purge", self.purge_tools, methods=["DELETE"], response_model=dict, status_code=200)
        self.router.add_api_route("/{uuid}", self.get_tool, methods=["GET"], response_model=ToolSchema, status_code=200)
        self.router.add_api_route("/{uuid}", self.update_tool, methods=["PUT"], response_model=None, status_code=204)
        self.router.add_api_route("/{uuid}", self.patch_tool, methods=["PATCH"], response_model=None, status_code=204)
        self.router.add_api_route("/{uuid}", self.delete_tool, methods=["DELETE"], response_model=None, status_code=204)
        self.router.add_api_route("/{uuid}/duplicate", self.duplicate_tool, methods=["POST"], response_model=ToolSchema, status_code=201)
        self.router.add_api_route("/recipe/{uuid_recipe}/step", self.duplicate_tool, methods=["POST"], response_model=ToolSchema, status_code=201)


    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))


    async def create_tool(self, payload: ToolCreateSchema) -> ToolCreatedSchema:
        """Create a new tool."""
        result = await self._service.create(Tool(name=payload.name))

        return ToolCreatedSchema(uuid=result.uuid)


    async def get_tool(self, uuid: StdUUID) -> ToolSchema:
        """Get a tool by UUID."""
        result = await self._service.read(self._to_uuid6(uuid))

        if result is None:
            self._logger.warning("⚠️ Tool not found via HTTP", uuid=str(uuid))
            raise HTTPException(status_code=404, detail="Tool not found")

        return ToolSchema.model_validate(result)


    async def list_tools(self) -> list[ToolSchema]:
        """List all tools."""
        return [ToolSchema.model_validate(tool) for tool in await self._service.find_all()]


    async def find_tools_by_name(self, name: str) -> list[ToolSchema]:
        """Find tools by name."""
        return [ToolSchema.model_validate(tool) for tool in await self._service.find_by_name(name)]


    async def update_tool(self, uuid: StdUUID, payload: ToolCreateSchema) -> None:
        """Update a tool by UUID."""
        await self._service.update(Tool(uuid=self._to_uuid6(uuid), name=payload.name))


    async def patch_tool(self, uuid: StdUUID, payload: ToolCreateSchema) -> None:
        """Patch a tool by UUID."""
        existing = await self._service.read(self._to_uuid6(uuid))

        if existing is None:
            self._logger.warning("⚠️ Tool not found for patching via HTTP", uuid=str(uuid))
            raise HTTPException(status_code=404, detail="Tool not found")

        updated_tool = Tool(
            uuid=self._to_uuid6(uuid),
            name=payload.name if payload.name is not None else existing.name
        )
        await self._service.update(updated_tool)


    async def delete_tool(self, uuid: StdUUID) -> None:
        """Delete a tool by UUID."""
        await self._service.delete(self._to_uuid6(uuid))


    async def purge_tools(self) -> dict:
        """Purge all soft-deleted tools that have exceeded the retention period."""
        purged = await self._service.purge()
        return {"purged": purged}


    async def duplicate_tool(self, uuid: StdUUID) -> ToolSchema:
        """Duplicate a tool by UUID."""
        result = await self._service.duplicate(self._to_uuid6(uuid))
        return ToolSchema.model_validate(result)