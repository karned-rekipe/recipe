from typing import Any

from application.use_cases import FindByNameUseCase
from arclith import BaseService, Logger
from domain.models.equipment import Equipment
from domain.models.ingredient import Ingredient
from domain.models.ingredient_group import IngredientGroup
from domain.models.ingredient_rayon import IngredientRayon
from domain.models.recipe import Recipe, RecipeStatus
from domain.models.recipe_equipment import RecipeEquipment
from domain.models.recipe_ingredient import RecipeIngredient
from domain.models.tag import Tag
from domain.ports.output.equipment_repository import EquipmentRepository
from domain.ports.output.ingredient_group_repository import IngredientGroupRepository
from domain.ports.output.ingredient_repository import IngredientRepository
from domain.ports.output.ingredient_rayon_repository import IngredientRayonRepository
from domain.ports.output.recipe_repository import RecipeRepository
from domain.ports.output.tag_repository import TagRepository
from uuid6 import UUID


class RecipeReferenceError(ValueError):
    """Raised when a recipe references an unknown catalog entity."""


class RecipeMergeConflict(ValueError):
    """Raised when a catalog merge would create an ambiguous recipe reference."""


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
    ) -> None:
        super().__init__(repository, logger, retention_days)
        self._recipe_repo = repository
        self._find_by_name_uc = FindByNameUseCase(repository, logger)
        self._ingredient_repo = ingredient_repository
        self._equipment_repo = equipment_repository
        self._tag_repo = tag_repository
        self._group_repo = group_repository
        self._rayon_repo = rayon_repository

    @property
    def repository(self) -> RecipeRepository:
        return self._recipe_repo

    async def create(self, entity: Recipe) -> Recipe:
        await self._ensure_references_exist(entity)
        enriched = entity.model_copy(update={"season_months": await self._calculate_recipe_season(entity)})
        return await super().create(enriched)

    async def update(self, entity: Recipe) -> Recipe:
        await self._ensure_references_exist(entity)
        enriched = entity.model_copy(update={"season_months": await self._calculate_recipe_season(entity)})
        return await super().update(enriched)

    async def find_by_name(self, name: str) -> list[Recipe]:
        return await self._find_by_name_uc.execute(name)

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
        missing_ingredients: list[str] = []
        if self._ingredient_repo is not None:
            for line in recipe.ingredients:
                if await self._ingredient_repo.read(UUID(str(line.ingredient_uuid))) is None:
                    missing_ingredients.append(str(line.ingredient_uuid))

        missing_equipment: list[str] = []
        if self._equipment_repo is not None:
            for line in recipe.equipment:
                if await self._equipment_repo.read(UUID(str(line.equipment_uuid))) is None:
                    missing_equipment.append(str(line.equipment_uuid))

        missing_tags: list[str] = []
        if self._tag_repo is not None:
            for tag_uuid in recipe.tag_uuids:
                if await self._tag_repo.read(UUID(str(tag_uuid))) is None:
                    missing_tags.append(str(tag_uuid))

        errors: list[str] = []
        if missing_ingredients:
            errors.append(f"Unknown ingredient UUID(s): {', '.join(missing_ingredients)}")
        if missing_equipment:
            errors.append(f"Unknown equipment UUID(s): {', '.join(missing_equipment)}")
        if missing_tags:
            errors.append(f"Unknown tag UUID(s): {', '.join(missing_tags)}")
        if errors:
            raise RecipeReferenceError("; ".join(errors))

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
        group = await self._read_group(ingredient.group_uuid) if ingredient is not None else None
        rayon = await self._read_rayon(ingredient.rayon_uuid) if ingredient is not None else None
        return {
            "ingredient_uuid": ingredient_uuid,
            "name": ingredient.name if ingredient is not None else f"Ingrédient {ingredient_uuid}",
            "quantity": line["quantity"],
            "unit": line["unit"],
            "season_months": ingredient.season_months if ingredient is not None else {},
            "rayon_uuid": str(ingredient.rayon_uuid) if ingredient is not None and ingredient.rayon_uuid is not None else None,
            "group_uuid": str(ingredient.group_uuid) if ingredient is not None and ingredient.group_uuid is not None else None,
            "rayon": self._catalog_payload(rayon),
            "group": self._catalog_payload(group),
            "green_score": ingredient.green_score if ingredient is not None else None,
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
