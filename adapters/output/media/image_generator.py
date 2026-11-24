from __future__ import annotations

import asyncio
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from domain.models.generated_image import GeneratedImage
from domain.ports.output.image_generator import ImageGenerator
from pydantic import ValidationError


class MediaImageGenerator(ImageGenerator):
    def __init__(self, base_url: str, timeout_seconds: float = 120.0) -> None:
        normalized_url = base_url.rstrip("/") + "/"
        scheme = urlsplit(normalized_url).scheme
        if scheme not in {"http", "https"}:
            raise ValueError("Media base URL must use http or https")
        self._base_url = normalized_url
        self._timeout_seconds = timeout_seconds

    async def generate(
        self,
        *,
        brief: str,
        bucket: str,
        object_prefix: str,
    ) -> GeneratedImage:
        response_payload = await asyncio.to_thread(
            self._post_json,
            {
                "brief": brief,
                "bucket": bucket,
                "object_prefix": object_prefix,
            },
        )
        try:
            return GeneratedImage.model_validate(response_payload)
        except ValidationError as exc:
            raise RuntimeError("Media service returned an invalid image payload") from exc

    def _post_json(self, payload: dict[str, object]) -> object:
        request = Request(
            urljoin(self._base_url, "v1/images/generate"),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            # The base URL scheme is restricted to HTTP(S) during initialization.
            with urlopen(request, timeout=self._timeout_seconds) as response:  # nosec B310
                return json.loads(response.read())
        except HTTPError as exc:
            raise RuntimeError(f"Media service rejected image generation with HTTP {exc.code}") from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError("Media service is unavailable") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Media service returned invalid JSON") from exc
