import json
from unittest.mock import MagicMock, patch

import pytest

from adapters.output.media import MediaRecipeImageGenerator


def _response_payload() -> dict:
    return {
        "image": {
            "bucket": "recipes",
            "key": "recipes/recipe-1/main/image.png",
            "url": "/api/media/v1/buckets/recipes/objects/recipes/recipe-1/main/image.png",
            "content_type": "image/png",
            "size_bytes": 42,
        },
        "provider": "openai",
    }


async def test_generate_posts_recipe_context_and_validates_response():
    response = MagicMock()
    response.read.return_value = json.dumps(_response_payload()).encode("utf-8")
    response.__enter__.return_value = response
    generator = MediaRecipeImageGenerator("http://media.test/base", timeout_seconds=10)

    with patch(
        "adapters.output.media.recipe_image_generator.urlopen",
        return_value=response,
    ) as urlopen_mock:
        generated = await generator.generate(
            recipe_uuid="recipe-1",
            recipe_name="Soupe",
            ingredients=["carotte", "oignon"],
        )

    request = urlopen_mock.call_args.args[0]
    assert request.full_url == "http://media.test/base/v1/recipe-images/generate"
    assert json.loads(request.data) == {
        "recipe_uuid": "recipe-1",
        "recipe_name": "Soupe",
        "ingredients": ["carotte", "oignon"],
        "prompt": None,
    }
    assert urlopen_mock.call_args.kwargs["timeout"] == 10
    assert generated.provider == "openai"
    assert generated.image.size_bytes == 42


def test_rejects_non_http_media_url():
    with pytest.raises(ValueError, match="http or https"):
        MediaRecipeImageGenerator("file:///tmp/media")


async def test_rejects_invalid_media_payload():
    response = MagicMock()
    response.read.return_value = b'{"provider":"openai"}'
    response.__enter__.return_value = response
    generator = MediaRecipeImageGenerator("http://media.test")

    with patch(
        "adapters.output.media.recipe_image_generator.urlopen",
        return_value=response,
    ):
        with pytest.raises(RuntimeError, match="invalid image payload"):
            await generator.generate(
                recipe_uuid="recipe-1",
                recipe_name="Soupe",
                ingredients=[],
            )
