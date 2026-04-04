from arclith.domain.ports.logger import Logger
from domain.models.recipe import Recipe
from domain.ports.output.recipe_repository import RecipeRepository


class FindByNameUseCase:
    def __init__(self, repository: RecipeRepository, logger: Logger) -> None:
        self._repository = repository
        self._logger = logger

    async def execute(self, name: str) -> list[Recipe]:
        self._logger.info("🔍 Finding recipes by name", name=name)
        result = [i for i in await self._repository.find_by_name(name) if not i.is_deleted]
        self._logger.info("✅ Recipes found", name=name, count=len(result))
        return result

