from __future__ import annotations

import os

from adapters.output.media import MediaRecipeImageGenerator
from domain.ports.output.recipe_image_generator import RecipeImageGenerator


def build_recipe_image_generator() -> RecipeImageGenerator:
    return MediaRecipeImageGenerator(
        os.getenv("RECIPE_MEDIA_API_BASE_URL", "http://127.0.0.1:8030"),
        timeout_seconds=float(os.getenv("RECIPE_MEDIA_API_TIMEOUT_SECONDS", "120")),
    )
