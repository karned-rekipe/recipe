from __future__ import annotations

import os

from adapters.output.media import MediaImageGenerator
from domain.ports.output.image_generator import ImageGenerator


def build_image_generator() -> ImageGenerator:
    return MediaImageGenerator(
        os.getenv("RECIPE_MEDIA_API_BASE_URL", "http://127.0.0.1:8030"),
        timeout_seconds=float(os.getenv("RECIPE_MEDIA_API_TIMEOUT_SECONDS", "120")),
    )
