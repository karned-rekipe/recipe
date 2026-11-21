from datetime import datetime, timezone

from arclith.adapters.output.memory.repository import InMemoryRepository
from domain.models.recipe import Recipe, RecipeStatus
from domain.models.recipe_filters import RecipeFilters, matches_recipe_filters
from domain.ports.output.recipe_repository import RecipeRepository
from uuid6 import UUID


class InMemoryRecipeRepository(InMemoryRepository[Recipe], RecipeRepository):
    def __init__(self) -> None:
        super().__init__()
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
        recipe = self._store.get(recipe_uuid)
        if recipe is None or recipe.is_deleted:
            return None
        if recipe.main_image and recipe.main_image.strip() and not replace_existing:
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
        recipe = self._store.get(recipe_uuid)
        if reservation is None or reservation[0] != reservation_id or recipe is None:
            return None
        if recipe.main_image and recipe.main_image.strip() and not replace_existing:
            return None
        updated = recipe.model_copy(update={
            "main_image": image_url,
            "updated_at": datetime.now(timezone.utc),
            "version": recipe.version + 1,
        })
        self._store[recipe_uuid] = updated
        self._image_generation_reservations.pop(recipe_uuid, None)
        return updated

    async def release_image_generation(self, recipe_uuid: UUID, reservation_id: str) -> None:
        reservation = self._image_generation_reservations.get(recipe_uuid)
        if reservation is not None and reservation[0] == reservation_id:
            self._image_generation_reservations.pop(recipe_uuid, None)

    async def find_by_name(self, name: str) -> list[Recipe]:
        return [i for i in self._store.values() if name.lower() in i.name.lower() and not i.is_deleted]

    async def find_page_by_name(self, name: str, offset: int = 0, limit: int | None = None) -> tuple[list[Recipe], int]:
        return await self.find_page_filtered(name=name, offset=offset, limit=limit)

    async def find_page_by_ingredient_uuid(
        self,
        ingredient_uuid: UUID,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Recipe], int]:
        return await self.find_page_filtered(ingredient_uuid=ingredient_uuid, offset=offset, limit=limit)

    async def find_page_by_equipment_uuid(
        self,
        equipment_uuid: UUID,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Recipe], int]:
        return await self.find_page_filtered(equipment_uuid=equipment_uuid, offset=offset, limit=limit)

    async def find_page_by_tag_uuid(
        self,
        tag_uuid: UUID,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Recipe], int]:
        return await self.find_page_filtered(tag_uuid=tag_uuid, offset=offset, limit=limit)

    async def find_by_component_recipe_uuid(self, recipe_uuid: UUID) -> list[Recipe]:
        return [
            recipe
            for recipe in self._store.values()
            if not recipe.is_deleted
            and any(str(component.recipe_uuid) == str(recipe_uuid) for component in recipe.components)
        ]

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
        filtered = [
            recipe
            for recipe in self._store.values()
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
        return any(
            not recipe.is_deleted and any(str(line.ingredient_uuid) == str(ingredient_uuid) for line in recipe.ingredients)
            for recipe in self._store.values()
        )

    async def exists_by_equipment_uuid(self, equipment_uuid: UUID) -> bool:
        return any(
            not recipe.is_deleted and any(str(line.equipment_uuid) == str(equipment_uuid) for line in recipe.equipment)
            for recipe in self._store.values()
        )

    async def exists_by_tag_uuid(self, tag_uuid: UUID) -> bool:
        return any(
            not recipe.is_deleted and any(str(item) == str(tag_uuid) for item in recipe.tag_uuids)
            for recipe in self._store.values()
        )
