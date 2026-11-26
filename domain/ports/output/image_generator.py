from abc import ABC, abstractmethod

from domain.models.generated_image import GeneratedImage


class ImageGenerationRateLimitError(RuntimeError):
    """Raised when an image provider rejects generation because capacity is unavailable."""


class ImageGenerator(ABC):
    @abstractmethod
    async def generate(
        self,
        *,
        brief: str,
        bucket: str,
        object_prefix: str,
    ) -> GeneratedImage:
        """Generate and store an image from a domain-owned free-form brief."""
