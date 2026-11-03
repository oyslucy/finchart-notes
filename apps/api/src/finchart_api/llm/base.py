from typing import Protocol

from finchart_api.domain.analysis import VisionResult


class VisionProviderError(Exception):
    """The provider could not produce a valid analysis."""


class VisionProvider(Protocol):
    async def analyze(self, image_bytes: bytes) -> VisionResult: ...
