from arclith.adapters.input.schemas import ApiResponse, success_response
from arclith.domain.ports.logger import Logger
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Annotated
from uuid import UUID as StdUUID
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
from application.services.step_service import StepService
from domain.models import Ingredient
from domain.models.recipe import Recipe
from domain.models.step import Step
from domain.models.ustensil import Ustensil


class RecipeRouter:
    def __init__(self, service: RecipeService, step_service: StepService, logger: Logger) -> None:
        self._service = service
        self._step_service = step_service
        self._logger = logger
        self.router = APIRouter(
            prefix = "/v1/recipes",
            tags = ["recipes"],
            dependencies = [Depends(inject_tenant_uri)],
        )
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route(
            methods = ["POST"],
            path = "/",
            endpoint = self.create_recipe,
            summary = "Create recipe",
            response_model = ApiResponse[RecipeCreatedSchema],
            response_description = "UUID of the created recipe",
            status_code = 201,
        )
        self.router.add_api_route(
            methods = ["GET"],
            path = "/",
            endpoint = self.list_recipes,
            summary = "List recipes",
            response_model = ApiResponse[list[RecipeSchema]],
            response_description = "List of active recipes with their linked data",
        )
        self.router.add_api_route(
            methods = ["DELETE"],
            path = "/purge",
            endpoint = self.purge_recipes,
            summary = "Purge soft-deleted recipes",
            response_model = ApiResponse[dict],
            response_description = "Number of permanently deleted records",
            status_code = 200,
        )
        self.router.add_api_route(
            methods = ["GET"],
            path = "/{uuid}",
            endpoint = self.get_recipe,
            summary = "Get recipe",
            response_model = ApiResponse[RecipeSchema],
            response_description = "The full recipe with linked ingredients, ustensils and steps",
            responses = {404: {"description": "Recipe not found"}},
        )
        self.router.add_api_route(
            methods = ["PUT"],
            path = "/{uuid}",
            endpoint = self.update_recipe,
            summary = "Replace recipe",
            status_code = 204,
            responses = {404: {"description": "Recipe not found"}},
            response_model = None,
        )
        self.router.add_api_route(
            methods = ["PATCH"],
            path = "/{uuid}",
            endpoint = self.patch_recipe,
            summary = "Partially update recipe",
            status_code = 204,
            responses = {404: {"description": "Recipe not found"}},
            response_model = None,
        )
        self.router.add_api_route(
            methods = ["DELETE"],
            path = "/{uuid}",
            endpoint = self.delete_recipe,
            summary = "Delete recipe",
            status_code = 204,
            response_model = None,
        )
        self.router.add_api_route(
            methods = ["POST"],
            path = "/{uuid}/duplicate",
            endpoint = self.duplicate_recipe,
            summary = "Duplicate recipe",
            response_model = ApiResponse[RecipeCreatedSchema],
            response_description = "UUID of the duplicated recipe",
            status_code = 201,
        )

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    async def create_recipe(self, payload: RecipeCreateSchema) -> ApiResponse[RecipeCreatedSchema]:
        """Create a new recipe."""
        recipe = Recipe(
            name = payload.name,
            description = payload.description,
            ingredients = [
                Ingredient(name = ing.name, unit = ing.unit) for ing in payload.ingredients
            ] if payload.ingredients else None,
            ustensils = [
                Ustensil(name = ust.name) for ust in payload.ustensils
            ] if payload.ustensils else None,
            steps = [
                Step(name = step.name, description = step.description, recipe_uuid = None)
                for step in payload.steps
            ] if payload.steps else None,
            nutriscore = payload.nutriscore,
        )
        result = await self._service.create(recipe)
        return success_response(
            data = RecipeCreatedSchema(uuid = result.uuid),
            links = {
                "self": f"/v1/recipes/{result.uuid}",
                "collection": "/v1/recipes",
                "steps": f"/v1/recipes/{result.uuid}/steps",
            },
        )

    async def get_recipe(self, uuid: StdUUID) -> ApiResponse[RecipeSchema]:
        """Get a recipe by its UUID, including linked ingredients, ustensils and steps."""
        result = await self._service.read(self._to_uuid6(uuid))
        if result is None:
            self._logger.warning("⚠️ Recipe not found via HTTP", uuid = str(uuid))
            raise HTTPException(status_code = 404, detail = "Recipe not found")
        steps = await self._step_service.find_by_recipe(self._to_uuid6(uuid))
        result = result.model_copy(update = {"steps": steps or None})
        return success_response(
            data = RecipeSchema.model_validate(result, from_attributes = True),
            links = {
                "self": f"/v1/recipes/{uuid}",
                "collection": "/v1/recipes",
                "steps": f"/v1/recipes/{uuid}/steps",
                "duplicate": f"/v1/recipes/{uuid}/duplicate",
            },
        )

    async def list_recipes(
            self,
            name: Annotated[str | None, Query(
                min_length = 1,
                description = "Filtre optionnel : recherche partielle sur le nom (insensible à la casse).",
                examples = ["Pizza"],
            )] = None,
            include_steps: Annotated[bool, Query(
                description = "Inclure les étapes associées à chaque recette.",
            )] = True,
    ) -> ApiResponse[list[RecipeSchema]]:
        """List all active (non-deleted) recipes."""
        items = await self._service.find_by_name(name) if name else await self._service.find_all()
        result: list[RecipeSchema] = []
        for recipe in items:
            if include_steps:
                steps = await self._step_service.find_by_recipe(recipe.uuid)
                enriched = recipe.model_copy(update = {"steps": steps or None})
                result.append(RecipeSchema.model_validate(enriched, from_attributes = True))
            else:
                result.append(RecipeSchema.model_validate(recipe, from_attributes = True))
        return success_response(data = result, links = {"self": "/v1/recipes"})

    async def update_recipe(self, uuid: StdUUID, payload: RecipeUpdateSchema) -> None:
        """Replace a recipe's content (PUT semantics)."""
        recipe = Recipe(
            uuid = self._to_uuid6(uuid),
            name = payload.name,
            description = payload.description,
            ingredients = [
                Ingredient(name = ing.name, unit = ing.unit) for ing in payload.ingredients
            ] if payload.ingredients else None,
            ustensils = [
                Ustensil(name = ust.name) for ust in payload.ustensils
            ] if payload.ustensils else None,
            steps = [
                Step(name = step.name, description = step.description, recipe_uuid = None)
                for step in payload.steps
            ] if payload.steps else None,
            nutriscore = payload.nutriscore,
        )
        await self._service.update(recipe)

    async def patch_recipe(self, uuid: StdUUID, payload: RecipePatchSchema) -> None:
        """Partially update a recipe (PATCH semantics)."""
        existing = await self._service.read(self._to_uuid6(uuid))
        if existing is None:
            self._logger.warning("⚠️ Recipe not found for patching via HTTP", uuid = str(uuid))
            raise HTTPException(status_code = 404, detail = "Recipe not found")
        await self._service.update(self._apply_patch(uuid, existing, payload))

    def _apply_patch(self, uuid: StdUUID, existing: Recipe, payload: RecipePatchSchema) -> Recipe:
        return Recipe(
            uuid = self._to_uuid6(uuid),
            name = payload.name if payload.name is not None else existing.name,
            description = payload.description if payload.description is not None else existing.description,
            ingredients = [
                Ingredient(name = ing.name, unit = ing.unit) for ing in payload.ingredients
            ] if payload.ingredients is not None else existing.ingredients,
            ustensils = [
                Ustensil(name = ust.name) for ust in payload.ustensils
            ] if payload.ustensils is not None else existing.ustensils,
            steps = [
                Step(name = step.name, description = step.description, recipe_uuid = None)
                for step in payload.steps
            ] if payload.steps is not None else existing.steps,
            nutriscore = payload.nutriscore if payload.nutriscore is not None else existing.nutriscore,
        )

    async def delete_recipe(self, uuid: StdUUID) -> None:
        """Soft-delete a recipe."""
        await self._service.delete(self._to_uuid6(uuid))

    async def purge_recipes(self) -> ApiResponse[dict]:
        """Permanently delete soft-deleted recipes that have exceeded the retention period."""
        purged = await self._service.purge()
        return success_response(data = {"purged": purged})

    async def duplicate_recipe(self, uuid: StdUUID) -> ApiResponse[RecipeCreatedSchema]:
        """Duplicate a recipe, assigning it a new UUID."""
        result = await self._service.duplicate(self._to_uuid6(uuid))
        return success_response(
            data = RecipeCreatedSchema(uuid = result.uuid),
            links = {
                "self": f"/v1/recipes/{result.uuid}",
                "collection": "/v1/recipes",
                "original": f"/v1/recipes/{uuid}",
            },
        )
