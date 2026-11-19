from typing import Annotated

from adapters.input.fastapi.dependencies import inject_tenant_uri
from adapters.input.schemas.ingredient_schema import UnitSchema
from application.services.ingredient_service import IngredientService
from arclith.adapters.input.fastapi.dependencies import get_duration_ms
from arclith.adapters.input.schemas.response_wrapper import ApiResponse, ResponseMetadata, success_response
from fastapi import APIRouter, Depends


class UnitRouter:
    def __init__(self, ingredient_service: IngredientService) -> None:
        self._ingredient_service = ingredient_service
        self.router = APIRouter(prefix="/v1/units", tags=["units"], dependencies=[Depends(inject_tenant_uri)])
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route(
            methods=["GET"],
            path="/",
            endpoint=self.list_units,
            summary="List reusable ingredient units",
            response_model=ApiResponse[list[UnitSchema]],
            status_code=200,
        )

    async def list_units(
        self,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
    ) -> ApiResponse[list[UnitSchema]]:
        return success_response(
            [UnitSchema.model_validate(item) for item in await self._ingredient_service.list_units()],
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )
