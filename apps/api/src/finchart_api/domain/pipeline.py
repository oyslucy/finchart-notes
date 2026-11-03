from dataclasses import dataclass

from finchart_api.domain.analysis import VisionResult
from finchart_api.imaging import PreparedImages, detect_mime, prepare_card_images, sha256_hex
from finchart_api.llm.base import VisionProvider


@dataclass(frozen=True)
class AnalyzedScreenshot:
    sha256: str
    vision: VisionResult
    images: PreparedImages


async def analyze_screenshot(image_bytes: bytes, provider: VisionProvider) -> AnalyzedScreenshot:
    detect_mime(image_bytes)
    vision = await provider.analyze(image_bytes)
    images = prepare_card_images(image_bytes, vision.analysis.bbox)
    return AnalyzedScreenshot(sha256=sha256_hex(image_bytes), vision=vision, images=images)
