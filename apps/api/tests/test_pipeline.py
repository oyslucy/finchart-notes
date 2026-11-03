from finchart_api.domain.pipeline import analyze_screenshot
from finchart_api.imaging import sha256_hex

from .conftest import FakeProvider


async def test_pipeline_analyzes_and_crops(png_bytes: bytes) -> None:
    provider = FakeProvider()

    result = await analyze_screenshot(png_bytes, provider)

    assert provider.calls == 1
    assert result.sha256 == sha256_hex(png_bytes)
    assert result.vision.model == "fake"
    assert result.images.cropped
    assert (result.images.width, result.images.height) == (516, 512)
