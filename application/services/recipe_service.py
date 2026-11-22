from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import uuid4

from application.use_cases import FindByNameUseCase
from arclith import BaseService, Logger
from domain.models.equipment import Equipment
from domain.models.generated_recipe_image import GeneratedRecipeImage
from domain.models.ingredient import Ingredient
from domain.models.ingredient_group import IngredientGroup
from domain.models.ingredient_rayon import IngredientRayon
from domain.models.recipe import Recipe, RecipeStatus
from domain.models.recipe_ai_enrichment import RecipeAIEnrichment
from domain.models.recipe_component import RecipeComponent
from domain.models.recipe_equipment import RecipeEquipment
from domain.models.recipe_ingredient import RecipeIngredient
from domain.models.recipe_line_origin import RecipeLineOrigin
from domain.models.tag import Tag
from domain.models.step import Step
from domain.ports.output.equipment_repository import EquipmentRepository
from domain.ports.output.ingredient_group_repository import IngredientGroupRepository
from domain.ports.output.ingredient_repository import IngredientRepository
from domain.ports.output.ingredient_rayon_repository import IngredientRayonRepository
from domain.ports.output.recipe_image_generator import RecipeImageGenerator
from domain.ports.output.recipe_ai_enrichment_agent import RecipeAIEnrichmentAgent
from domain.ports.output.recipe_repository import RecipeRepository
from domain.ports.output.tag_repository import TagRepository
from uuid6 import UUID


class RecipeReferenceError(ValueError):
    """Raised when a recipe references an unknown catalog entity."""


class RecipeMergeConflict(ValueError):
    """Raised when a catalog merge would create an ambiguous recipe reference."""


class RecipeComponentCycleError(ValueError):
    """Raised when recipe components would create a recursive recipe graph."""


class RecipeComponentInUseError(ValueError):
    """Raised when deleting a recipe still used as a component."""


class RecipeImageAlreadyExistsError(ValueError):
    """Raised when image generation would replace an existing main image."""


class RecipeImageGenerationUnavailableError(RuntimeError):
    """Raised when no recipe image generator is configured."""


class RecipeImageGenerationInProgressError(RuntimeError):
    """Raised when another request already generates an image for the recipe."""


class RecipeImageGenerationConflictError(RuntimeError):
    """Raised when the image reservation expires or the recipe changes."""


class RecipeAIEnrichmentUnavailableError(RuntimeError):
    """Raised when no internal recipe AI agent is configured."""


class _ReadableRepository(Protocol):
    async def read(self, uuid: UUID) -> object | None: ...


class RecipeService(BaseService[Recipe]):
    def __init__(
        self,
        repository: RecipeRepository,
        logger: Logger,
        retention_days: float | None = None,
        ingredient_repository: IngredientRepository | None = None,
        equipment_repository: EquipmentRepository | None = None,
        tag_repository: TagRepository | None = None,
        group_repository: IngredientGroupRepository | None = None,
        rayon_repository: IngredientRayonRepository | None = None,
        image_generator: RecipeImageGenerator | None = None,
        ai_enrichment_agent: RecipeAIEnrichmentAgent | None = None,
    ) -> None:
        super().__init__(repository, logger, retention_days)
        self._recipe_repo = repository
        self._find_by_name_uc = FindByNameUseCase(repository, logger)
        self._ingredient_repo = ingredient_repository
        self._equipment_repo = equipment_repository
        self._tag_repo = tag_repository
        self._group_repo = group_repository
        self._rayon_repo = rayon_repository
        self._image_generator = image_generator
        self._ai_enrichment_agent = ai_enrichment_agent

    @property
    def repository(self) -> RecipeRepository:
        return self._recipe_repo

    async def create(self, entity: Recipe) -> Recipe:
        enriched = await self._prepare_for_save(entity)
        return await super().create(enriched)

    async def update(self, entity: Recipe) -> Recipe:
        enriched = await self._prepare_for_save(entity)
        updated = await super().update(enriched)
        await self._propagate_component_change(updated.uuid, visited={str(updated.uuid)})
        return updated

    async def delete(self, uuid: UUID, deleted_by: str | None = None) -> None:
        parents = await self._recipe_repo.find_by_component_recipe_uuid(uuid)
        if parents:
            parent_names = ", ".join(parent.name for parent in parents[:5])
            raise RecipeComponentInUseError(f"Recipe is used as a component by: {parent_names}")
        await super().delete(uuid, deleted_by)

    async def find_by_name(self, name: str) -> list[Recipe]:
        return await self._find_by_name_uc.execute(name)

    async def generate_main_image(
        self,
        uuid: UUID,
        *,
        prompt: str | None = None,
        replace_existing: bool = False,
    ) -> tuple[Recipe, GeneratedRecipeImage]:
        image_generator = self._image_generator
        if image_generator is None:
            raise RecipeImageGenerationUnavailableError("Recipe image generation is not configured")

        reservation_id = str(uuid4())
        recipe = await self._reserve_main_image_generation(
            uuid,
            reservation_id,
            replace_existing=replace_existing,
        )
        try:
            generated = await image_generator.generate(
                recipe_uuid=str(recipe.uuid),
                recipe_name=recipe.name,
                ingredients=await self._image_ingredient_names(recipe),
                prompt=prompt,
            )
            updated = await self._complete_main_image_generation(
                uuid,
                reservation_id,
                generated.image.url,
                replace_existing=replace_existing,
            )
            return updated, generated
        except BaseException:
            await self._recipe_repo.release_image_generation(uuid, reservation_id)
            raise

    async def enrich_with_ai(
        self,
        uuid: UUID,
        *,
        generate_image: bool = True,
    ) -> tuple[Recipe, RecipeAIEnrichment]:
        agent = self._ai_enrichment_agent
        if agent is None:
            raise RecipeAIEnrichmentUnavailableError("Recipe AI enrichment is not configured")
        if await self.read(uuid) is None:
            raise KeyError(f"Recipe with uuid {uuid} not found")

        result = await agent.enrich(
            recipe_uuid=str(uuid),
            generate_image=generate_image,
        )
        updated = await self.read(uuid)
        if updated is None:
            raise KeyError(f"Recipe with uuid {uuid} not found after AI enrichment")
        return updated, result

    async def _reserve_main_image_generation(
        self,
        uuid: UUID,
        reservation_id: str,
        *,
        replace_existing: bool,
    ) -> Recipe:
        current = await self.read(uuid)
        self._ensure_image_generation_allowed(current, uuid, replace_existing=replace_existing)
        recipe = await self._recipe_repo.reserve_image_generation(
            uuid,
            reservation_id,
            datetime.now(timezone.utc) + timedelta(minutes=5),
            replace_existing=replace_existing,
        )
        if recipe is not None:
            return recipe
        latest = await self.read(uuid)
        self._ensure_image_generation_allowed(latest, uuid, replace_existing=replace_existing)
        raise RecipeImageGenerationInProgressError("Recipe image generation is already in progress")

    @staticmethod
    def _ensure_image_generation_allowed(
        recipe: Recipe | None,
        uuid: UUID,
        *,
        replace_existing: bool,
    ) -> None:
        if recipe is None:
            raise KeyError(f"Recipe with uuid {uuid} not found")
        if recipe.main_image and recipe.main_image.strip() and not replace_existing:
            raise RecipeImageAlreadyExistsError("Recipe already has a main image")

    async def _image_ingredient_names(self, recipe: Recipe) -> list[str]:
        hydrated = await self.hydrate_recipe(recipe)
        return [
            ingredient["name"]
            for ingredient in hydrated["ingredients"]
            if isinstance(ingredient.get("name"), str) and ingredient["name"].strip()
        ]

    async def _complete_main_image_generation(
        self,
        uuid: UUID,
        reservation_id: str,
        image_url: str,
        *,
        replace_existing: bool,
    ) -> Recipe:
        updated = await self._recipe_repo.complete_image_generation(
            uuid,
            reservation_id,
            image_url,
            replace_existing=replace_existing,
        )
        if updated is None:
            raise RecipeImageGenerationConflictError(
                "Recipe changed while its image was being generated"
            )
        return updated

    async def find_page_filtered(
        self,
        name: str | None = None,
        ingredient_uuid: UUID | None = None,
        equipment_uuid: UUID | None = None,
        tag_uuid: UUID | None = None,
        difficulty: int | None = None,
        origin_country: str | None = None,
        price: int | None = None,
        favorite: bool | None = None,
        season_month: int | None = None,
        status: RecipeStatus | None = None,
        meal_planner_eligible: bool | None = None,
        has_main_image: bool | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Recipe], int]:
        """Return a page of recipes (optionally filtered by name) and total count."""
        return await self._recipe_repo.find_page_filtered(
            name=name,
            ingredient_uuid=ingredient_uuid,
            equipment_uuid=equipment_uuid,
            tag_uuid=tag_uuid,
            difficulty=difficulty,
            origin_country=origin_country,
            price=price,
            favorite=favorite,
            season_month=season_month,
            status=status,
            meal_planner_eligible=meal_planner_eligible,
            has_main_image=has_main_image,
            offset=offset,
            limit=limit,
        )

    async def hydrate_recipe(self, recipe: Recipe) -> dict[str, Any]:
        data = recipe.model_dump(mode="json", exclude_computed_fields=True)
        data["is_deleted"] = recipe.is_deleted
        data["steps"] = [self._step_to_schema_payload(step) for step in recipe.steps]
        data["ingredients"] = [
            await self._hydrate_ingredient_line(line.model_dump(mode="json"), await self._read_ingredient(line.ingredient_uuid))
            for line in recipe.ingredients
        ]
        data["components"] = await self._hydrate_components(recipe.components)
        data["equipment"] = [
            self._hydrate_equipment_line(line.model_dump(mode="json"), await self._read_equipment(line.equipment_uuid))
            for line in recipe.equipment
        ]
        data["tags"] = [
            tag.model_dump(mode="json", exclude_computed_fields=True)
            for tag in [await self._read_tag(tag_uuid) for tag_uuid in recipe.tag_uuids]
            if tag is not None
        ]
        return data

    async def hydrate_recipes(self, recipes: list[Recipe]) -> list[dict[str, Any]]:
        return [await self.hydrate_recipe(recipe) for recipe in recipes]

    async def read_hydrated(self, uuid: UUID) -> dict[str, Any] | None:
        recipe = await self.read(uuid)
        if recipe is None:
            return None
        return await self.hydrate_recipe(recipe)

    async def find_page_filtered_hydrated(
        self,
        name: str | None = None,
        ingredient_uuid: UUID | None = None,
        equipment_uuid: UUID | None = None,
        tag_uuid: UUID | None = None,
        difficulty: int | None = None,
        origin_country: str | None = None,
        price: int | None = None,
        favorite: bool | None = None,
        season_month: int | None = None,
        status: RecipeStatus | None = None,
        meal_planner_eligible: bool | None = None,
        has_main_image: bool | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        recipes, total = await self.find_page_filtered(
            name=name,
            ingredient_uuid=ingredient_uuid,
            equipment_uuid=equipment_uuid,
            tag_uuid=tag_uuid,
            difficulty=difficulty,
            origin_country=origin_country,
            price=price,
            favorite=favorite,
            season_month=season_month,
            status=status,
            meal_planner_eligible=meal_planner_eligible,
            has_main_image=has_main_image,
            offset=offset,
            limit=limit,
        )
        return await self.hydrate_recipes(recipes), total

    async def replace_ingredient_reference(self, source_uuid: UUID, target_uuid: UUID) -> int:
        recipes, _ = await self.find_page_filtered(ingredient_uuid=source_uuid, limit=None)
        for recipe in recipes:
            if any(str(line.ingredient_uuid) == str(target_uuid) for line in recipe.ingredients):
                raise RecipeMergeConflict(
                    f"Recipe {recipe.uuid} already uses target ingredient {target_uuid}"
                )

        for recipe in recipes:
            updated_lines = [
                self._replace_ingredient_line(line, source_uuid, target_uuid)
                for line in recipe.ingredients
            ]
            await self.update(recipe.model_copy(update={"ingredients": updated_lines}))
        return len(recipes)

    async def replace_equipment_reference(self, source_uuid: UUID, target_uuid: UUID) -> int:
        recipes, _ = await self.find_page_filtered(equipment_uuid=source_uuid, limit=None)
        for recipe in recipes:
            if any(str(line.equipment_uuid) == str(target_uuid) for line in recipe.equipment):
                raise RecipeMergeConflict(
                    f"Recipe {recipe.uuid} already uses target equipment {target_uuid}"
                )

        for recipe in recipes:
            updated_lines = [
                self._replace_equipment_line(line, source_uuid, target_uuid)
                for line in recipe.equipment
            ]
            await self.update(recipe.model_copy(update={"equipment": updated_lines}))
        return len(recipes)

    async def is_ingredient_used(self, ingredient_uuid: UUID) -> bool:
        return await self._recipe_repo.exists_by_ingredient_uuid(ingredient_uuid)

    async def is_equipment_used(self, equipment_uuid: UUID) -> bool:
        return await self._recipe_repo.exists_by_equipment_uuid(equipment_uuid)

    async def is_tag_used(self, tag_uuid: UUID) -> bool:
        return await self._recipe_repo.exists_by_tag_uuid(tag_uuid)

    async def _ensure_references_exist(self, recipe: Recipe) -> None:
        missing_references = await self._missing_references(recipe)
        errors = _reference_errors(missing_references)
        if errors:
            raise RecipeReferenceError("; ".join(errors))

        await self._ensure_component_graph_is_acyclic(recipe)

    async def _missing_references(self, recipe: Recipe) -> dict[str, list[str]]:
        return {
            "ingredient": await self._missing_ingredients(recipe),
            "equipment": await self._missing_equipment(recipe),
            "tag": await self._missing_tags(recipe),
            "component recipe": await self._missing_components(recipe),
        }

    async def _missing_ingredients(self, recipe: Recipe) -> list[str]:
        if self._ingredient_repo is None:
            return []
        return await _missing_repository_references(
            self._ingredient_repo,
            [line.ingredient_uuid for line in recipe.ingredients],
        )

    async def _missing_equipment(self, recipe: Recipe) -> list[str]:
        if self._equipment_repo is None:
            return []
        return await _missing_repository_references(
            self._equipment_repo,
            [line.equipment_uuid for line in recipe.equipment],
        )

    async def _missing_tags(self, recipe: Recipe) -> list[str]:
        if self._tag_repo is None:
            return []
        return await _missing_repository_references(self._tag_repo, recipe.tag_uuids)

    async def _missing_components(self, recipe: Recipe) -> list[str]:
        missing: list[str] = []
        for component in recipe.components:
            if await self.read(UUID(str(component.recipe_uuid))) is None:
                missing.append(str(component.recipe_uuid))
        return missing

    async def _read_ingredient(self, ingredient_uuid: object) -> Ingredient | None:
        if self._ingredient_repo is None:
            return None
        return await self._ingredient_repo.read(UUID(str(ingredient_uuid)))

    async def _read_equipment(self, equipment_uuid: object) -> Equipment | None:
        if self._equipment_repo is None:
            return None
        return await self._equipment_repo.read(UUID(str(equipment_uuid)))

    async def _read_tag(self, tag_uuid: object) -> Tag | None:
        if self._tag_repo is None:
            return None
        return await self._tag_repo.read(UUID(str(tag_uuid)))

    async def _read_group(self, group_uuid: object | None) -> IngredientGroup | None:
        if self._group_repo is None or group_uuid is None:
            return None
        return await self._group_repo.read(UUID(str(group_uuid)))

    async def _read_rayon(self, rayon_uuid: object | None) -> IngredientRayon | None:
        if self._rayon_repo is None or rayon_uuid is None:
            return None
        return await self._rayon_repo.read(UUID(str(rayon_uuid)))

    async def _hydrate_ingredient_line(self, line: dict[str, Any], ingredient: Ingredient | None) -> dict[str, Any]:
        ingredient_uuid = line["ingredient_uuid"]
        group, rayon = await self._ingredient_catalog_entries(ingredient)
        payload = {
            "ingredient_uuid": ingredient_uuid,
            "quantity": line["quantity"],
            "unit": line["unit"],
            "component_uuid": line.get("component_uuid"),
            "source_recipe_uuid": line.get("source_recipe_uuid"),
            "line_origin": line.get("line_origin") or RecipeLineOrigin.manual.value,
        }
        payload.update(self._ingredient_line_payload(ingredient, ingredient_uuid, group, rayon))
        return payload

    async def _ingredient_catalog_entries(
        self,
        ingredient: Ingredient | None,
    ) -> tuple[IngredientGroup | None, IngredientRayon | None]:
        if ingredient is None:
            return None, None
        return (
            await self._read_group(ingredient.group_uuid),
            await self._read_rayon(ingredient.rayon_uuid),
        )

    def _ingredient_line_payload(
        self,
        ingredient: Ingredient | None,
        ingredient_uuid: object,
        group: IngredientGroup | None,
        rayon: IngredientRayon | None,
    ) -> dict[str, Any]:
        if ingredient is None:
            return self._missing_ingredient_line_payload(ingredient_uuid)
        return {
            "name": ingredient.name,
            "season_months": ingredient.season_months,
            "rayon_uuid": _optional_uuid_text(ingredient.rayon_uuid),
            "group_uuid": _optional_uuid_text(ingredient.group_uuid),
            "main_supplier_uuid": _optional_uuid_text(ingredient.main_supplier_uuid),
            "secondary_supplier_uuids": [str(uuid) for uuid in ingredient.secondary_supplier_uuids],
            "rayon": self._catalog_payload(rayon),
            "group": self._catalog_payload(group),
            "green_score": ingredient.green_score,
        }

    @staticmethod
    def _missing_ingredient_line_payload(ingredient_uuid: object) -> dict[str, Any]:
        return {
            "name": f"Ingrédient {ingredient_uuid}",
            "season_months": {},
            "rayon_uuid": None,
            "group_uuid": None,
            "main_supplier_uuid": None,
            "secondary_supplier_uuids": [],
            "rayon": None,
            "group": None,
            "green_score": None,
        }

    @staticmethod
    def _hydrate_equipment_line(line: dict[str, Any], equipment: Equipment | None) -> dict[str, Any]:
        equipment_uuid = line["equipment_uuid"]
        return {
            "equipment_uuid": equipment_uuid,
            "name": equipment.name if equipment is not None else f"Équipement {equipment_uuid}",
            "quantity": line.get("quantity"),
        }

    @staticmethod
    def _step_to_schema_payload(step: Any) -> dict[str, Any]:
        data = step.model_dump(mode="json")
        data["is_deleted"] = step.is_deleted
        return data

    async def _calculate_recipe_season(self, recipe: Recipe) -> dict[int, int]:
        ingredient_seasons: list[dict[int, int]] = []
        for line in recipe.ingredients:
            ingredient = await self._read_ingredient(line.ingredient_uuid)
            if ingredient is not None and ingredient.season_months:
                ingredient_seasons.append(ingredient.season_months)

        if not ingredient_seasons:
            return {month: 1 for month in range(1, 13)}

        aggregated: dict[int, int] = {}
        for month in range(1, 13):
            scores = [season[month] for season in ingredient_seasons if month in season]
            if scores:
                score = round(sum(scores) / len(scores))
                aggregated[month] = max(1, min(3, score))
        return aggregated

    async def _prepare_for_save(self, recipe: Recipe) -> Recipe:
        await self._ensure_references_exist(recipe)
        projected = await self._with_component_projection(recipe)
        season_months = await self._calculate_recipe_season(projected)
        return projected.model_copy(
            update={
                "season_months": season_months,
                "status": self._status_for_lines(projected),
            }
        )

    async def _with_component_projection(self, recipe: Recipe) -> Recipe:
        manual_ingredients = [
            self._as_manual_ingredient(line)
            for line in recipe.ingredients
            if line.line_origin != RecipeLineOrigin.component_projection
        ]
        manual_steps = [
            step
            for step in recipe.steps
            if step.line_origin != RecipeLineOrigin.component_projection
        ]

        projected_ingredients: list[RecipeIngredient] = []
        projected_steps: list[Step] = []
        components = sorted(recipe.components, key=lambda component: component.rank)
        for component in components:
            child = await self.read(UUID(str(component.recipe_uuid)))
            if child is None:
                continue
            projected_ingredients.extend(self._project_ingredients_for_component(component, child))
            projected_steps.extend(self._project_steps_for_component(component, child))

        ranked_steps = self._rank_steps([*manual_steps, *projected_steps])
        return recipe.model_copy(
            update={
                "components": components,
                "ingredients": [*manual_ingredients, *projected_ingredients],
                "steps": ranked_steps,
            }
        )

    def _as_manual_ingredient(self, line: RecipeIngredient) -> RecipeIngredient:
        if line.line_origin == RecipeLineOrigin.manual and line.component_uuid is None and line.source_recipe_uuid is None:
            return line
        return line.model_copy(
            update={
                "component_uuid": None,
                "source_recipe_uuid": None,
                "line_origin": RecipeLineOrigin.manual,
            }
        )

    @staticmethod
    def _project_ingredients_for_component(component: RecipeComponent, child: Recipe) -> list[RecipeIngredient]:
        return [
            line.model_copy(
                update={
                    "quantity": line.quantity * component.servings_multiplier,
                    "component_uuid": component.uuid,
                    "source_recipe_uuid": component.recipe_uuid,
                    "line_origin": RecipeLineOrigin.component_projection,
                }
            )
            for line in child.ingredients
        ]

    @staticmethod
    def _project_steps_for_component(component: RecipeComponent, child: Recipe) -> list[Step]:
        return [
            Step(
                name=step.name,
                description=step.description,
                cooking_time=step.cooking_time,
                rest_time=step.rest_time,
                preparation_time=step.preparation_time,
                secondary_images=list(step.secondary_images),
                main_image=step.main_image,
                rank=step.rank,
                component_uuid=component.uuid,
                source_recipe_uuid=component.recipe_uuid,
                line_origin=RecipeLineOrigin.component_projection,
            )
            for step in child.steps
        ]

    @staticmethod
    def _rank_steps(steps: list[Step]) -> list[Step]:
        return [
            step.model_copy(update={"rank": rank})
            for rank, step in enumerate(sorted(steps, key=lambda item: item.rank), 1)
        ]

    @staticmethod
    def _status_for_lines(recipe: Recipe) -> RecipeStatus:
        if recipe.status == RecipeStatus.archived:
            return RecipeStatus.archived
        return RecipeStatus.active if recipe.ingredients else RecipeStatus.draft

    async def _ensure_component_graph_is_acyclic(self, recipe: Recipe) -> None:
        for component in recipe.components:
            if str(component.recipe_uuid) == str(recipe.uuid):
                raise RecipeComponentCycleError("A recipe cannot include itself as a component")
            if await self._component_path_reaches(
                start_uuid=UUID(str(component.recipe_uuid)),
                target_uuid=UUID(str(recipe.uuid)),
                seen=set(),
            ):
                raise RecipeComponentCycleError("Recipe components cannot create a cycle")

    async def _component_path_reaches(self, *, start_uuid: UUID, target_uuid: UUID, seen: set[str]) -> bool:
        start_key = str(start_uuid)
        if start_key == str(target_uuid):
            return True
        if start_key in seen:
            return False
        seen.add(start_key)

        recipe = await self.read(start_uuid)
        if recipe is None:
            return False
        for component in recipe.components:
            if await self._component_path_reaches(
                start_uuid=UUID(str(component.recipe_uuid)),
                target_uuid=target_uuid,
                seen=seen,
            ):
                return True
        return False

    async def _propagate_component_change(self, recipe_uuid: UUID, *, visited: set[str]) -> None:
        parents = await self._recipe_repo.find_by_component_recipe_uuid(recipe_uuid)
        for parent in parents:
            parent_key = str(parent.uuid)
            if parent_key in visited:
                continue
            visited.add(parent_key)
            projected_parent = await self._prepare_for_save(parent)
            updated_parent = await super().update(projected_parent)
            await self._propagate_component_change(updated_parent.uuid, visited=visited)

    async def _hydrate_components(self, components: list[RecipeComponent]) -> list[dict[str, Any]]:
        hydrated: list[dict[str, Any]] = []
        for component in sorted(components, key=lambda item: item.rank):
            child = await self.read(UUID(str(component.recipe_uuid)))
            component_data = component.model_dump(mode="json")
            if child is None:
                component_data["recipe_name"] = None
                component_data["ingredients"] = []
                component_data["steps"] = []
                hydrated.append(component_data)
                continue

            projected_ingredients = self._project_ingredients_for_component(component, child)
            component_data["recipe_name"] = child.name
            component_data["ingredients"] = [
                await self._hydrate_ingredient_line(
                    line.model_dump(mode="json"),
                    await self._read_ingredient(line.ingredient_uuid),
                )
                for line in projected_ingredients
            ]
            component_data["steps"] = [
                self._step_to_schema_payload(step)
                for step in self._rank_steps(self._project_steps_for_component(component, child))
            ]
            hydrated.append(component_data)
        return hydrated

    @staticmethod
    def _catalog_payload(item: IngredientGroup | IngredientRayon | None) -> dict[str, Any] | None:
        if item is None:
            return None
        return item.model_dump(mode="json", exclude_computed_fields=True)

    @staticmethod
    def _replace_ingredient_line(line: RecipeIngredient, source_uuid: UUID, target_uuid: UUID) -> RecipeIngredient:
        if str(line.ingredient_uuid) != str(source_uuid):
            return line
        return line.model_copy(update={"ingredient_uuid": target_uuid})

    @staticmethod
    def _replace_equipment_line(line: RecipeEquipment, source_uuid: UUID, target_uuid: UUID) -> RecipeEquipment:
        if str(line.equipment_uuid) != str(source_uuid):
            return line
        return line.model_copy(update={"equipment_uuid": target_uuid})


async def _missing_repository_references(
    repository: _ReadableRepository,
    uuids: Iterable[object],
) -> list[str]:
    missing: list[str] = []
    for uuid in uuids:
        if await repository.read(UUID(str(uuid))) is None:
            missing.append(str(uuid))
    return missing


def _reference_errors(missing_references: dict[str, list[str]]) -> list[str]:
    return [
        f"Unknown {reference_type} UUID(s): {', '.join(uuids)}"
        for reference_type, uuids in missing_references.items()
        if uuids
    ]


def _optional_uuid_text(value: UUID | None) -> str | None:
    return str(value) if value is not None else None
