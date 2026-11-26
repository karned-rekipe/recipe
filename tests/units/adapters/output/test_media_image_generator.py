import json
from io import BytesIO
from urllib.error import HTTPError
from unittest.mock import MagicMock, patch

import pytest

from adapters.output.media import MediaImageGenerator
from domain.ports.output.image_generator import ImageGenerationRateLimitError


def _response_payload() -> dict:
    return {
        "image": {
            "bucket": "equipment",
            "key": "equipment/equipment-1/main/image.png",
            "url": "/api/media/v1/buckets/equipment/objects/equipment/equipment-1/main/image.png",
            "content_type": "image/png",
            "size_bytes": 42,
        },
        "provider": "openai",
    }


async def test_generate_posts_generic_brief_and_storage_metadata():
    response = MagicMock()
    response.read.return_value = json.dumps(_response_payload()).encode("utf-8")
    response.__enter__.return_value = response
    generator = MediaImageGenerator("http://media.test/base", timeout_seconds=10)

    with patch(
        "adapters.output.media.image_generator.urlopen",
        return_value=response,
    ) as urlopen_mock:
        generated = await generator.generate(
            brief="Photo produit d'un fouet de cuisine, fond neutre",
            bucket="equipment",
            object_prefix="equipment/equipment-1/main",
        )

    request = urlopen_mock.call_args.args[0]
    assert request.full_url == "http://media.test/base/v1/images/generate"
    assert json.loads(request.data) == {
        "brief": "Photo produit d'un fouet de cuisine, fond neutre",
        "bucket": "equipment",
        "object_prefix": "equipment/equipment-1/main",
    }
    assert urlopen_mock.call_args.kwargs["timeout"] == 10
    assert generated.provider == "openai"
    assert generated.image.size_bytes == 42


def test_rejects_non_http_media_url():
    with pytest.raises(ValueError, match="http or https"):
        MediaImageGenerator("file:///tmp/media")


async def test_rejects_invalid_media_payload():
    response = MagicMock()
    response.read.return_value = b'{"provider":"openai"}'
    response.__enter__.return_value = response
    generator = MediaImageGenerator("http://media.test")

    with patch(
        "adapters.output.media.image_generator.urlopen",
        return_value=response,
    ):
        with pytest.raises(RuntimeError, match="invalid image payload"):
            await generator.generate(
                brief="Brief valide",
                bucket="equipment",
                object_prefix="equipment/equipment-1/main",
            )


async def test_propagates_media_rate_limit_detail():
    generator = MediaImageGenerator("http://media.test")
    media_error = HTTPError(
        "http://media.test/v1/images/generate",
        429,
        "Too Many Requests",
        hdrs=None,
        fp=BytesIO(
            b'{"detail":"Les credits OpenAI de generation d images sont epuises."}'
        ),
    )

    with patch(
        "adapters.output.media.image_generator.urlopen",
        side_effect=media_error,
    ):
        with pytest.raises(ImageGenerationRateLimitError, match="credits OpenAI"):
            await generator.generate(
                brief="Brief valide",
                bucket="equipment",
                object_prefix="equipment/equipment-1/main",
            )
