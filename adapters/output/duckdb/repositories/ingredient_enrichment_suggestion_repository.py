from arclith.adapters.output.duckdb.repository import DuckDBRepository
from domain.models.ingredient_enrichment_suggestion import IngredientEnrichmentSuggestion
from domain.ports.output.ingredient_enrichment_suggestion_repository import IngredientEnrichmentSuggestionRepository
from uuid6 import UUID


class DuckDBIngredientEnrichmentSuggestionRepository(
    DuckDBRepository[IngredientEnrichmentSuggestion],
    IngredientEnrichmentSuggestionRepository,
):
    def __init__(self, path: str) -> None:
        super().__init__(path, IngredientEnrichmentSuggestion)

    async def find_by_ingredient_uuid(self, ingredient_uuid: UUID) -> list[IngredientEnrichmentSuggestion]:
        rows = self._fetch(
            f"SELECT * FROM {self._table} WHERE deleted_at IS NULL AND ingredient_uuid = ?",  # nosec B608
            [str(ingredient_uuid)],
        )
        return [self._row_to_entity(row) for row in rows]

    async def find_pending_by_ingredient_uuid(self, ingredient_uuid: UUID) -> list[IngredientEnrichmentSuggestion]:
        rows = self._fetch(
            f"SELECT * FROM {self._table} "  # nosec B608
            "WHERE deleted_at IS NULL AND ingredient_uuid = ? AND status = 'pending'",
            [str(ingredient_uuid)],
        )
        return [self._row_to_entity(row) for row in rows]
