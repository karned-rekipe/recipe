from adapters.output.media import MediaRecipeImageGenerator
from infrastructure.containers.recipe_image_generator_container import build_recipe_image_generator


def test_build_recipe_image_generator_uses_environment(monkeypatch):
    monkeypatch.setenv("RECIPE_MEDIA_API_BASE_URL", "https://media.example.test/base")
    monkeypatch.setenv("RECIPE_MEDIA_API_TIMEOUT_SECONDS", "42")

    generator = build_recipe_image_generator()

    assert isinstance(generator, MediaRecipeImageGenerator)
    assert generator._base_url == "https://media.example.test/base/"
    assert generator._timeout_seconds == 42
