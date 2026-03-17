from arclith import Logger
from fastapi import APIRouter, Depends, HTTPException
from uuid6 import UUID
from uuid import UUID as StdUUID

from adapters.input.fastapi.dependencies import inject_tenant_uri
from adapters.input.schemas.recipe_schema import RecipeSchema, RecipeCreateSchema
from application.services.recipe_service import RecipeService
from domain.models.recipe import Recipe


class RecipeRouter:
    def __init__(self, service: RecipeService, logger: Logger) -> None:
        self._service = service
        self._logger = logger
        self.router = APIRouter(
            prefix="/v1/recipes",
            tags=["recipes"],
            dependencies=[Depends(inject_tenant_uri)]
        )
        self._register_routes()


    def _register_routes(self) -> None:
        self.router.add_api_route("/", self.create_recipe, methods=["POST"], response_model=RecipeSchema, status_code=201)
        self.router.add_api_route("/", self.list_recipes, methods=["GET"], response_model=list[RecipeSchema], status_code=200)
        self.router.add_api_route("/{name}", self.find_recipes_by_name, methods=["GET"], response_model=list[RecipeSchema], status_code=200)
        self.router.add_api_route("/purge", self.purge_recipes, methods=["DELETE"], response_model=dict, status_code=200)
        self.router.add_api_route("/{uuid}", self.get_recipe, methods=["GET"], response_model=RecipeSchema, status_code=200)
        self.router.add_api_route("/{uuid}", self.update_recipe, methods=["PUT"], response_model=None, status_code=204)
        self.router.add_api_route("/{uuid}", self.patch_recipe, methods=["PATCH"], response_model=None, status_code=204)
        self.router.add_api_route("/{uuid}", self.delete_recipe, methods=["DELETE"], response_model=None, status_code=204)
        self.router.add_api_route("/{uuid}/duplicate", self.duplicate_recipe, methods=["POST"], response_model=RecipeSchema, status_code=201)


    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))


    async def create_recipe(self, payload: RecipeCreateSchema) -> RecipeSchema:
        """Create a new recipe."""
        result = await self._service.create(Recipe(name=payload.name))

        return RecipeSchema.model_validate(result)


    async def get_recipe(self, uuid: StdUUID) -> RecipeSchema:
        """Get a recipe by UUID."""
        result = await self._service.read(self._to_uuid6(uuid))

        if result is None:
            self._logger.warning("⚠️ Recipe not found via HTTP", uuid=str(uuid))
            raise HTTPException(status_code=404, detail="Recipe not found")

        return RecipeSchema.model_validate(result)


    async def list_recipes(self) -> list[RecipeSchema]:
        """List all recipes."""
        return [RecipeSchema.model_validate(recipe) for recipe in await self._service.find_all()]


    async def find_recipes_by_name(self, name: str) -> list[RecipeSchema]:
        """Find recipes by name."""
        return [RecipeSchema.model_validate(recipe) for recipe in await self._service.find_by_name(name)]


    async def update_recipe(self, uuid: StdUUID, payload: RecipeCreateSchema) -> None:
        """Update a recipe by UUID."""
        await self._service.update(Recipe(uuid=self._to_uuid6(uuid), name=payload.name))


    async def patch_recipe(self, uuid: StdUUID, payload: RecipeCreateSchema) -> None:
        """Patch a recipe by UUID."""
        existing = await self._service.read(self._to_uuid6(uuid))

        if existing is None:
            self._logger.warning("⚠️ Recipe not found for patching via HTTP", uuid=str(uuid))
            raise HTTPException(status_code=404, detail="Recipe not found")

        updated_recipe = Recipe(
            uuid=self._to_uuid6(uuid),
            name=payload.name if payload.name is not None else existing.name
        )
        await self._service.update(updated_recipe)


    async def delete_recipe(self, uuid: StdUUID) -> None:
        """Delete a recipe by UUID."""
        await self._service.delete(self._to_uuid6(uuid))


    async def purge_recipes(self) -> dict:
        """Purge all soft-deleted recipes that have exceeded the retention period."""
        purged = await self._service.purge()
        return {"purged": purged}


    async def duplicate_recipe(self, uuid: StdUUID) -> RecipeSchema:
        """Duplicate a recipe by UUID."""
        result = await self._service.duplicate(self._to_uuid6(uuid))
        return RecipeSchema.model_validate(result)