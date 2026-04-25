from arclith import BaseService, Logger
from domain.models.ingredient_group import IngredientGroup
from domain.ports.output.ingredient_group_repository import IngredientGroupRepository


class IngredientGroupService(BaseService[IngredientGroup]):
    def __init__(self, repository: IngredientGroupRepository, logger: Logger, retention_days: float | None = None) -> None:
        super().__init__(repository, logger, retention_days)
        self._group_repo = repository

    @property
    def repository(self) -> IngredientGroupRepository:
        return self._group_repo

    async def find_by_name(self, name: str) -> list[IngredientGroup]:
        result = [item for item in await self._group_repo.find_by_name(name) if not item.is_deleted]
        return sorted(result, key=lambda item: (item.sort_order, item.name.casefold()))

    async def find_page_filtered(
        self,
        name: str | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[IngredientGroup], int]:
        if name:
            return await self._group_repo.find_page_by_name(name, offset, limit)
        return await self._group_repo.find_page(offset, limit)
