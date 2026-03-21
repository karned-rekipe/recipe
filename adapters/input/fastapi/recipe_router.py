from typing import Annotated
from uuid import UUID as StdUUID

from arclith.domain.ports.logger import Logger
from fastapi import APIRouter, Depends, HTTPException, Query
from uuid6 import UUID

from adapters.input.fastapi.dependencies import inject_tenant_uri
from adapters.input.schemas.recipe_schema import (
    RecipeCreateSchema,
    RecipeCreatedSchema,
    RecipePatchSchema,
    RecipeSchema,
    RecipeUpdateSchema,
)
from application.services.recipe_service import RecipeService
from domain.models import Ingredient
from domain.models.recipe import Recipe
from domain.models.step import Step
from domain.models.ustensil import Ustensil


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
        self.router.add_api_route("/", self.create_recipe, methods=["POST"], response_model=RecipeCreatedSchema, status_code=201)
        self.router.add_api_route("/", self.list_recipes, methods=["GET"], response_model=list[RecipeSchema], status_code=200)
        self.router.add_api_route("/purge", self.purge_recipes, methods=["DELETE"], response_model=dict, status_code=200)
        self.router.add_api_route("/{uuid}", self.get_recipe, methods=["GET"], response_model=RecipeSchema, status_code=200)
        self.router.add_api_route("/{uuid}", self.update_recipe, methods=["PUT"], response_model=None, status_code=204)
        self.router.add_api_route("/{uuid}", self.patch_recipe, methods=["PATCH"], response_model=None, status_code=204)
        self.router.add_api_route("/{uuid}", self.delete_recipe, methods=["DELETE"], response_model=None, status_code=204)
        self.router.add_api_route("/{uuid}/duplicate", self.duplicate_recipe, methods = ["POST"],
                                  response_model = RecipeCreatedSchema, status_code = 201)


    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))


    async def create_recipe(self, payload: RecipeCreateSchema) -> RecipeCreatedSchema:
        """Create a new recipe."""
        recipe = Recipe(
            name=payload.name,
            description=payload.description,
            ingredients=[
                Ingredient(name=ing.name, unit=ing.unit)
                for ing in payload.ingredients
            ] if payload.ingredients else None,
            ustensils=[
                Ustensil(name=ust.name)
                for ust in payload.ustensils
            ] if payload.ustensils else None,
            steps=[
                Step(name = step.name, description = step.description, recipe_uuid = None)
                for step in payload.steps
            ] if payload.steps else None,
            nutriscore=payload.nutriscore
        )
        result = await self._service.create(recipe)

        return RecipeCreatedSchema(uuid=result.uuid)


    async def get_recipe(self, uuid: StdUUID) -> RecipeSchema:
        """Get a recipe by UUID."""
        result = await self._service.read(self._to_uuid6(uuid))

        if result is None:
            self._logger.warning("⚠️ Recipe not found via HTTP", uuid=str(uuid))
            raise HTTPException(status_code=404, detail="Recipe not found")

        return RecipeSchema.model_validate(result, from_attributes = True)

    async def list_recipes(
            self,
            name: Annotated[str | None, Query(
                min_length = 1,
                description = "Filtre par nom (recherche partielle, insensible à la casse).",
                examples = ["Pizza"],
            )] = None,
    ) -> list[RecipeSchema]:
        """List all recipes, optionally filtered by name."""
        items = await self._service.find_by_name(name) if name else await self._service.find_all()
        return [RecipeSchema.model_validate(recipe, from_attributes = True) for recipe in items]

    async def update_recipe(self, uuid: StdUUID, payload: RecipeUpdateSchema) -> None:
        """Update a recipe by UUID."""
        recipe = Recipe(
            uuid=self._to_uuid6(uuid),
            name=payload.name,
            description=payload.description,
            ingredients=[
                Ingredient(name=ing.name, unit=ing.unit)
                for ing in payload.ingredients
            ] if payload.ingredients else None,
            ustensils=[
                Ustensil(name=ust.name)
                for ust in payload.ustensils
            ] if payload.ustensils else None,
            steps=[
                Step(name = step.name, description = step.description, recipe_uuid = None)
                for step in payload.steps
            ] if payload.steps else None,
            nutriscore=payload.nutriscore
        )
        await self._service.update(recipe)

    async def patch_recipe(self, uuid: StdUUID, payload: RecipePatchSchema) -> None:
        """Patch a recipe by UUID."""
        existing = await self._service.read(self._to_uuid6(uuid))

        if existing is None:
            self._logger.warning("⚠️ Recipe not found for patching via HTTP", uuid=str(uuid))
            raise HTTPException(status_code=404, detail="Recipe not found")

        updated_recipe = Recipe(
            uuid=self._to_uuid6(uuid),
            name=payload.name if payload.name is not None else existing.name,
            description=payload.description if payload.description is not None else existing.description,
            ingredients=[
                Ingredient(name=ing.name, unit=ing.unit)
                for ing in payload.ingredients
            ] if payload.ingredients is not None else existing.ingredients,
            ustensils=[
                Ustensil(name=ust.name)
                for ust in payload.ustensils
            ] if payload.ustensils is not None else existing.ustensils,
            steps=[
                Step(name = step.name, description = step.description, recipe_uuid = None)
                for step in payload.steps
            ] if payload.steps is not None else existing.steps,
            nutriscore=payload.nutriscore if payload.nutriscore is not None else existing.nutriscore
        )
        await self._service.update(updated_recipe)


    async def delete_recipe(self, uuid: StdUUID) -> None:
        """Delete a recipe by UUID."""
        await self._service.delete(self._to_uuid6(uuid))


    async def purge_recipes(self) -> dict:
        """Purge all soft-deleted recipes that have exceeded the retention period."""
        purged = await self._service.purge()
        return {"purged": purged}

    async def duplicate_recipe(self, uuid: StdUUID) -> RecipeCreatedSchema:
        """Duplicate a recipe by UUID."""
        result = await self._service.duplicate(self._to_uuid6(uuid))
        return RecipeCreatedSchema(uuid = result.uuid)
