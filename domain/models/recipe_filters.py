from dataclasses import dataclass

from domain.models.recipe import Recipe, RecipeStatus
from uuid6 import UUID


@dataclass(frozen=True)
class RecipeFilters:
    name: str | None = None
    ingredient_uuid: UUID | None = None
    equipment_uuid: UUID | None = None
    tag_uuid: UUID | None = None
    difficulty: int | None = None
    origin_country: str | None = None
    price: int | None = None
    favorite: bool | None = None
    season_month: int | None = None
    status: RecipeStatus | None = None
    meal_planner_eligible: bool | None = None


def matches_recipe_filters(recipe: Recipe, filters: RecipeFilters) -> bool:
    return all((
        not recipe.is_deleted,
        _matches_status(recipe, filters),
        _matches_meal_planner_eligibility(recipe, filters.meal_planner_eligible),
        _matches_name(recipe, filters.name),
        _matches_ingredient(recipe, filters.ingredient_uuid),
        _matches_equipment(recipe, filters.equipment_uuid),
        _matches_tag(recipe, filters.tag_uuid),
        _matches_value(recipe.difficulty, filters.difficulty),
        _matches_origin_country(recipe, filters.origin_country),
        _matches_value(recipe.price, filters.price),
        _matches_value(recipe.favorite, filters.favorite),
        _matches_season_month(recipe, filters.season_month),
    ))


def _matches_status(recipe: Recipe, filters: RecipeFilters) -> bool:
    expected = RecipeStatus.active if filters.meal_planner_eligible else filters.status
    return _matches_value(recipe.status, expected)


def _matches_meal_planner_eligibility(recipe: Recipe, eligible: bool | None) -> bool:
    return not eligible or bool(recipe.ingredients)


def _matches_name(recipe: Recipe, name: str | None) -> bool:
    return name is None or name.lower() in recipe.name.lower()


def _matches_ingredient(recipe: Recipe, ingredient_uuid: UUID | None) -> bool:
    return ingredient_uuid is None or any(
        str(line.ingredient_uuid) == str(ingredient_uuid)
        for line in recipe.ingredients
    )


def _matches_equipment(recipe: Recipe, equipment_uuid: UUID | None) -> bool:
    return equipment_uuid is None or any(
        str(line.equipment_uuid) == str(equipment_uuid)
        for line in recipe.equipment
    )


def _matches_tag(recipe: Recipe, tag_uuid: UUID | None) -> bool:
    return tag_uuid is None or any(str(item) == str(tag_uuid) for item in recipe.tag_uuids)


def _matches_origin_country(recipe: Recipe, origin_country: str | None) -> bool:
    value = getattr(recipe.origin_country, "value", recipe.origin_country)
    return _matches_value(value, origin_country)


def _matches_value(actual: object, expected: object | None) -> bool:
    return expected is None or actual == expected


def _matches_season_month(recipe: Recipe, season_month: int | None) -> bool:
    return season_month is None or recipe.season_months.get(season_month, 0) > 0
