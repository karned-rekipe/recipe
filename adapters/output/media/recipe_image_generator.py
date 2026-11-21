from __future__ import annotations

import asyncio
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from domain.models.generated_recipe_image import GeneratedRecipeImage
from domain.ports.output.recipe_image_generator import RecipeImageGenerator
from pydantic import ValidationError


class MediaRecipeImageGenerator(RecipeImageGenerator):
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
        recipe_uuid: str,
        recipe_name: str,
        ingredients: list[str],
        prompt: str | None = None,
    ) -> GeneratedRecipeImage:
        payload: dict[str, object] = {
            "recipe_uuid": recipe_uuid,
            "recipe_name": recipe_name,
            "ingredients": ingredients,
            "prompt": prompt,
        }
        response_payload = await asyncio.to_thread(self._post_json, payload)
        try:
            return GeneratedRecipeImage.model_validate(response_payload)
        except ValidationError as exc:
            raise RuntimeError("Media service returned an invalid image payload") from exc

    def _post_json(self, payload: dict[str, object]) -> object:
        request = Request(
            urljoin(self._base_url, "v1/recipe-images/generate"),
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
