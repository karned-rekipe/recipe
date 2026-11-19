from arclith import BaseService, Logger
from domain.models.ingredient_rayon import IngredientRayon
from domain.ports.output.ingredient_rayon_repository import IngredientRayonRepository


class IngredientRayonService(BaseService[IngredientRayon]):
    def __init__(self, repository: IngredientRayonRepository, logger: Logger, retention_days: float | None = None) -> None:
        super().__init__(repository, logger, retention_days)
        self._rayon_repo = repository

    @property
    def repository(self) -> IngredientRayonRepository:
        return self._rayon_repo

    async def find_by_name(self, name: str) -> list[IngredientRayon]:
        result = [item for item in await self._rayon_repo.find_by_name(name) if not item.is_deleted]
        return sorted(result, key=lambda item: (item.sort_order, item.name.casefold()))

    async def find_page_filtered(
        self,
        name: str | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[IngredientRayon], int]:
        if name:
            return await self._rayon_repo.find_page_by_name(name, offset, limit)
        return await self._rayon_repo.find_page(offset, limit)
