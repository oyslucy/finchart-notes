import os

import pytest

from finchart_api.llm.gemini import GeminiProvider

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("GEMINI_API_KEY"), reason="GEMINI_API_KEY not set"),
]


async def test_gemini_returns_valid_analysis(png_bytes: bytes) -> None:
    provider = GeminiProvider(
        api_key=os.environ["GEMINI_API_KEY"],
        model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        fallback_model=None,
    )

    result = await provider.analyze(png_bytes)

    assert len(result.analysis.bbox) == 4
