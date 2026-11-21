import pytest

from domain.models.recipe import Recipe
from domain.models.recipe_filters import RecipeFilters, matches_recipe_filters


@pytest.mark.parametrize(
    ("main_image", "has_main_image", "expected"),
    [
        (None, None, True),
        (None, False, True),
        ("", False, True),
        ("   ", False, True),
        ("https://example.com/recipe.jpg", False, False),
        ("https://example.com/recipe.jpg", True, True),
    ],
)
def test_matches_main_image_filter(
    main_image: str | None,
    has_main_image: bool | None,
    expected: bool,
) -> None:
    recipe = Recipe(name="Recette", main_image=main_image)

    assert matches_recipe_filters(
        recipe,
        RecipeFilters(has_main_image=has_main_image),
    ) is expected
