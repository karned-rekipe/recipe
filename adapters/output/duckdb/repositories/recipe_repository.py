import json
from datetime import datetime, timezone
from typing import Any

from arclith.adapters.output.duckdb.repository import DuckDBRepository
from domain.models.recipe import Recipe, RecipeStatus
from domain.models.recipe_filters import RecipeFilters, matches_recipe_filters
from domain.ports.output.recipe_repository import RecipeRepository
from uuid6 import UUID


class DuckDBRecipeRepository(DuckDBRepository[Recipe], RecipeRepository):
    def __init__(self, path: str) -> None:
        super().__init__(path, Recipe)
        self._image_generation_reservations: dict[UUID, tuple[str, datetime]] = {}

    async def reserve_image_generation(
        self,
        recipe_uuid: UUID,
        reservation_id: str,
        expires_at: datetime,
        *,
        replace_existing: bool,
    ) -> Recipe | None:
        now = datetime.now(timezone.utc)
        reservation = self._image_generation_reservations.get(recipe_uuid)
        if reservation is not None and reservation[1] > now:
            return None
        recipe = await self.read(recipe_uuid)
        if recipe is None or (recipe.main_image and recipe.main_image.strip() and not replace_existing):
            return None
        self._image_generation_reservations[recipe_uuid] = (reservation_id, expires_at)
        return recipe

    async def complete_image_generation(
        self,
        recipe_uuid: UUID,
        reservation_id: str,
        image_url: str,
        *,
        replace_existing: bool,
    ) -> Recipe | None:
        reservation = self._image_generation_reservations.get(recipe_uuid)
        recipe = await self.read(recipe_uuid)
        if reservation is None or reservation[0] != reservation_id or recipe is None:
            return None
        if recipe.main_image and recipe.main_image.strip() and not replace_existing:
            return None
        updated = recipe.model_copy(update={
            "main_image": image_url,
            "updated_at": datetime.now(timezone.utc),
            "version": recipe.version + 1,
        })
        await self.update(updated)
        self._image_generation_reservations.pop(recipe_uuid, None)
        return updated

    async def release_image_generation(self, recipe_uuid: UUID, reservation_id: str) -> None:
        reservation = self._image_generation_reservations.get(recipe_uuid)
        if reservation is not None and reservation[0] == reservation_id:
            self._image_generation_reservations.pop(recipe_uuid, None)

    def _entity_to_row(self, entity: Recipe) -> dict[str, Any]:
        row = entity.model_dump(mode="json", exclude_computed_fields=True)
        row["uuid"] = str(row["uuid"])
        row["sources"] = json.dumps(row["sources"])
        row["components"] = json.dumps(row["components"])
        row["ingredients"] = json.dumps(row["ingredients"])
        row["equipment"] = json.dumps(row["equipment"])
        row["steps"] = json.dumps(row["steps"])
        row["tag_uuids"] = json.dumps(row["tag_uuids"])
        row["season_months"] = json.dumps(row["season_months"])
        row["secondary_images"] = json.dumps(row["secondary_images"])
        return row

    def _row_to_entity(self, row: dict[str, Any]) -> Recipe:
        cleaned = dict(row)
        for field_name in (
            "sources",
            "components",
            "ingredients",
            "equipment",
            "steps",
            "tag_uuids",
            "season_months",
            "secondary_images",
        ):
            value = cleaned.get(field_name)
            if isinstance(value, str) and value:
                cleaned[field_name] = json.loads(value)
        return super()._row_to_entity(cleaned)

    # noinspection SqlNoDataSourceInspection
    async def find_by_name(self, name: str) -> list[Recipe]:
        rows = self._fetch(
            f"SELECT * FROM {self._table} WHERE deleted_at IS NULL AND lower(name) LIKE ?",  # nosec B608
            [f"%{name.lower()}%"],
        )
        return [self._row_to_entity(r) for r in rows]

    # noinspection SqlNoDataSourceInspection
    async def find_page_by_name(self, name: str, offset: int = 0, limit: int | None = None) -> tuple[list[Recipe], int]:
        return await self.find_page_filtered(name=name, offset=offset, limit=limit)

    # noinspection SqlNoDataSourceInspection
    async def find_by_component_recipe_uuid(self, recipe_uuid: UUID) -> list[Recipe]:
        rows = self._fetch(
            f"SELECT * FROM {self._table} WHERE deleted_at IS NULL ORDER BY rowid",  # nosec B608
            [],
        )
        recipe_uuid_text = str(recipe_uuid)
        recipes = [self._row_to_entity(row) for row in rows]
        return [
            recipe
            for recipe in recipes
            if any(str(component.recipe_uuid) == recipe_uuid_text for component in recipe.components)
        ]

    async def find_page_by_ingredient_uuid(
        self,
        ingredient_uuid: UUID,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Recipe], int]:
        return await self._find_page_by_reference("ingredient_uuid", ingredient_uuid, offset, limit)

    async def find_page_by_equipment_uuid(
        self,
        equipment_uuid: UUID,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Recipe], int]:
        return await self._find_page_by_reference("equipment_uuid", equipment_uuid, offset, limit)

    async def find_page_by_tag_uuid(
        self,
        tag_uuid: UUID,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Recipe], int]:
        return await self.find_page_filtered(tag_uuid=tag_uuid, offset=offset, limit=limit)

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
        rows = self._fetch(
            f"SELECT * FROM {self._table} WHERE deleted_at IS NULL ORDER BY rowid",  # nosec B608
            [],
        )
        recipes = [self._row_to_entity(row) for row in rows]
        filtered = [
            recipe
            for recipe in recipes
            if matches_recipe_filters(
                recipe,
                RecipeFilters(
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
                ),
            )
        ]
        total = len(filtered)
        page = filtered[offset: offset + limit] if limit is not None else filtered[offset:]
        return page, total

    async def exists_by_ingredient_uuid(self, ingredient_uuid: UUID) -> bool:
        items, _ = await self.find_page_by_ingredient_uuid(ingredient_uuid, 0, 1)
        return bool(items)

    async def exists_by_equipment_uuid(self, equipment_uuid: UUID) -> bool:
        items, _ = await self.find_page_by_equipment_uuid(equipment_uuid, 0, 1)
        return bool(items)

    async def exists_by_tag_uuid(self, tag_uuid: UUID) -> bool:
        items, _ = await self.find_page_by_tag_uuid(tag_uuid, 0, 1)
        return bool(items)

    async def _find_page_by_reference(
        self,
        field_name: str,
        uuid: UUID,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Recipe], int]:
        rows = self._fetch(
            f"SELECT * FROM {self._table} WHERE deleted_at IS NULL ORDER BY rowid",  # nosec B608
            [],
        )
        recipes = [self._row_to_entity(r) for r in rows]
        uuid_text = str(uuid)
        if field_name == "ingredient_uuid":
            filtered = [
                recipe
                for recipe in recipes
                if any(str(line.ingredient_uuid) == uuid_text for line in recipe.ingredients)
            ]
        else:
            filtered = [
                recipe
                for recipe in recipes
                if any(str(line.equipment_uuid) == uuid_text for line in recipe.equipment)
            ]
        total = len(filtered)
        page = filtered[offset: offset + limit] if limit is not None else filtered[offset:]
        return page, total
