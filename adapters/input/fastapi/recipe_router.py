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
            prefix="/v1/recipes",
            tags=["recipes"],
            dependencies=[Depends(inject_tenant_uri)]
        )
        self._register_routes()


    def _register_routes(self) -> None:
        self.router.add_api_route("/", self.create_recipe, methods = ["POST"], response_model = RecipeCreatedSchema,
                                  status_code = 201,
                                  summary = "Create recipe", response_description = "UUID of the created recipe")
        self.router.add_api_route("/", self.list_recipes, methods = ["GET"], response_model = list[RecipeSchema],
                                  status_code = 200,
                                  summary = "List recipes",
                                  response_description = "List of active recipes with their linked data")
        self.router.add_api_route("/purge", self.purge_recipes, methods = ["DELETE"], response_model = dict,
                                  status_code = 200,
                                  summary = "Purge soft-deleted recipes",
                                  response_description = "Number of permanently deleted records")
        self.router.add_api_route("/{uuid}", self.get_recipe, methods = ["GET"], response_model = RecipeSchema,
                                  status_code = 200,
                                  summary = "Get recipe",
                                  response_description = "The full recipe with linked ingredients, ustensils and steps",
                                  responses = {404: {"description": "Recipe not found"}})
        self.router.add_api_route("/{uuid}", self.update_recipe, methods = ["PUT"], response_model = None,
                                  status_code = 204,
                                  summary = "Replace recipe", responses = {404: {"description": "Recipe not found"}})
        self.router.add_api_route("/{uuid}", self.patch_recipe, methods = ["PATCH"], response_model = None,
                                  status_code = 204,
                                  summary = "Partially update recipe",
                                  responses = {404: {"description": "Recipe not found"}})
        self.router.add_api_route("/{uuid}", self.delete_recipe, methods = ["DELETE"], response_model = None,
                                  status_code = 204,
                                  summary = "Delete recipe")
        self.router.add_api_route("/{uuid}/duplicate", self.duplicate_recipe, methods = ["POST"],
                                  response_model = RecipeCreatedSchema, status_code = 201,
                                  summary = "Duplicate recipe", response_description = "UUID of the duplicated recipe")


    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))


    async def create_recipe(self, payload: RecipeCreateSchema) -> RecipeCreatedSchema:
        """Create a new recipe.

        Returns the UUID of the created recipe.
        Workflow — after creation, attach content using:
        - `POST /v1/recipes/{uuid}/steps` to add preparation steps
        - `POST /v1/recipes/{uuid}/ingredients/{ingredient_uuid}` to link existing ingredients
        - `POST /v1/recipes/{uuid}/ustensils/{ustensil_uuid}` to link existing ustensils

        Inline ingredients/ustensils/steps can also be passed directly in the body (they are created on the fly).
        """
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
        """Get a recipe by its UUID.

        Returns the full recipe including all linked ingredients, ustensils and steps.
        Fields: uuid, name, description, nutriscore, ingredients (list), ustensils (list), steps (list), created_at, updated_at, version.
        """
        result = await self._service.read(self._to_uuid6(uuid))

        if result is None:
            self._logger.warning("⚠️ Recipe not found via HTTP", uuid=str(uuid))
            raise HTTPException(status_code=404, detail="Recipe not found")

        steps = await self._step_service.find_by_recipe(self._to_uuid6(uuid))
        result = result.model_copy(update = {"steps": steps or None})

        return RecipeSchema.model_validate(result, from_attributes = True)

    async def list_recipes(
            self,
            name: Annotated[str | None, Query(
                min_length = 1,
                description = "Filtre optionnel : recherche partielle sur le nom, insensible à la casse. Ex: 'pizza' retournera toutes les recettes dont le nom contient 'pizza'.",
                examples = ["Pizza"],
            )] = None,
            include_steps: Annotated[bool, Query(
                description = "Inclure ou non les étapes associées à chaque recette. "
                              "Mettre à false pour éviter un appel supplémentaire par recette.",
            )] = True,
    ) -> list[RecipeSchema]:
        """List all active (non-deleted) recipes.

        Pass `name` for a partial, case-insensitive name filter.

        By default (`include_steps=true`), each recipe includes its full linked data:
        ingredients, ustensils and steps. When `include_steps=false`, the steps are not
        fetched from the step store, which avoids one additional query per recipe.

        Steps are fetched from the step store (created via POST /v1/recipes/{uuid}/steps).
        Fields per item: uuid, name, description, nutriscore, ingredients, ustensils, steps,
        created_at, updated_at, version.
        """
        items = await self._service.find_by_name(name) if name else await self._service.find_all()
        result: list[RecipeSchema] = []
        for recipe in items:
            if include_steps:
                steps = await self._step_service.find_by_recipe(recipe.uuid)
                enriched = recipe.model_copy(update = {"steps": steps or None})
                result.append(RecipeSchema.model_validate(enriched, from_attributes = True))
            else:
                result.append(RecipeSchema.model_validate(recipe, from_attributes = True))
        return result

    async def update_recipe(self, uuid: StdUUID, payload: RecipeUpdateSchema) -> None:
        """Replace a recipe's content (PUT semantics).

        Fully overwrites name, description, nutriscore, and inline ingredients/ustensils/steps.
        To manage links independently, prefer the dedicated sub-resources:
        `POST /v1/recipes/{uuid}/ingredients/{ingredient_uuid}`, `POST /v1/recipes/{uuid}/ustensils/{ustensil_uuid}`,
        `POST /v1/recipes/{uuid}/steps`.
        """
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
        """Partially update a recipe (PATCH semantics).

        Only the fields provided in the body are updated; omitted fields keep their current value.
        """
        existing = await self._service.read(self._to_uuid6(uuid))

        if existing is None:
            self._logger.warning("⚠️ Recipe not found for patching via HTTP", uuid=str(uuid))
            raise HTTPException(status_code=404, detail="Recipe not found")

        await self._service.update(self._apply_patch(uuid, existing, payload))

    def _apply_patch(self, uuid: StdUUID, existing: Recipe, payload: RecipePatchSchema) -> Recipe:
        return Recipe(
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


    async def delete_recipe(self, uuid: StdUUID) -> None:
        """Soft-delete a recipe.

        The recipe is marked as deleted and excluded from list results.
        It is retained until the purge retention period expires.
        Use `DELETE /v1/recipes/purge` to permanently remove expired entries.
        """
        await self._service.delete(self._to_uuid6(uuid))


    async def purge_recipes(self) -> dict:
        """Permanently delete soft-deleted recipes that have exceeded the retention period.

        Returns {"purged": <count>} with the number of permanently deleted records.
        This operation is irreversible.
        """
        purged = await self._service.purge()
        return {"purged": purged}

    async def duplicate_recipe(self, uuid: StdUUID) -> RecipeCreatedSchema:
        """Duplicate a recipe, assigning it a new UUID.

        Creates a full copy including all linked ingredients, ustensils and steps.
        Returns the UUID of the new recipe.
        """
        result = await self._service.duplicate(self._to_uuid6(uuid))
        return RecipeCreatedSchema(uuid = result.uuid)
