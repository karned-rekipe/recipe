from arclith import BaseService, Logger

from application.use_cases import FindByNameUseCase
from domain.models.ingredient import Ingredient
from domain.ports.output.ingredient_repository import IngredientRepository


class IngredientService(BaseService[Ingredient]):
    def __init__(self, repository: IngredientRepository, logger: Logger, retention_days: float | None = None) -> None:
        super().__init__(repository, logger, retention_days)
        self._find_by_name_uc: FindByNameUseCase[Ingredient] = FindByNameUseCase(repository, logger)

    async def find_by_name(self, name: str) -> list[Ingredient]:
        return await self._find_by_name_uc.execute(name)

