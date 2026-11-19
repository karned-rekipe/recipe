from arclith.adapters.output.memory.repository import InMemoryRepository
from domain.models.recipe import Recipe, RecipeStatus
from domain.ports.output.recipe_repository import RecipeRepository
from uuid6 import UUID


class InMemoryRecipeRepository(InMemoryRepository[Recipe], RecipeRepository):
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
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Recipe], int]:
        filtered = [
            recipe
            for recipe in self._store.values()
            if self._matches_filters(
                recipe,
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

    @staticmethod
    def _matches_filters(
        recipe: Recipe,
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
    ) -> bool:
        if recipe.is_deleted:
            return False
        expected_status = RecipeStatus.active if meal_planner_eligible else status
        if expected_status is not None and recipe.status != expected_status:
            return False
        if meal_planner_eligible and not recipe.ingredients:
            return False
        if name and name.lower() not in recipe.name.lower():
            return False
        if ingredient_uuid is not None and not any(str(line.ingredient_uuid) == str(ingredient_uuid) for line in recipe.ingredients):
            return False
        if equipment_uuid is not None and not any(str(line.equipment_uuid) == str(equipment_uuid) for line in recipe.equipment):
            return False
        if tag_uuid is not None and not any(str(item) == str(tag_uuid) for item in recipe.tag_uuids):
            return False
        if difficulty is not None and recipe.difficulty != difficulty:
            return False
        if origin_country is not None:
            recipe_origin = getattr(recipe.origin_country, "value", recipe.origin_country)
            if recipe_origin != origin_country:
                return False
        if price is not None and recipe.price != price:
            return False
        if favorite is not None and recipe.favorite != favorite:
            return False
        return season_month is None or recipe.season_months.get(season_month, 0) > 0
