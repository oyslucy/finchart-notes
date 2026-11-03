import io

import pytest
from PIL import Image, ImageDraw

from finchart_api.domain.analysis import ChartAnalysis, VisionResult


def make_png(width: int = 1000, height: int = 800) -> bytes:
    img = Image.new("RGB", (width, height), "white")
    ImageDraw.Draw(img).rectangle((100, 200, 600, 700), outline="black", width=4)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_analysis(bbox: list[int] | None = None) -> ChartAnalysis:
    return ChartAnalysis(
        bbox=bbox or [250, 100, 875, 600],
        title="KOSPI 일봉",
        chart_type="candlestick",
        period="2026-01 ~ 2026-10",
        takeaways=["약 2,600에서 3,100까지 상승했다."],
        interpretation="상승 추세가 이어졌다.",
        caveats=["로그 스케일 여부를 확인할 수 없다."],
    )


class FakeProvider:
    def __init__(self, analysis: ChartAnalysis | None = None) -> None:
        self.analysis = analysis or make_analysis()
        self.calls = 0

    async def analyze(self, image_bytes: bytes) -> VisionResult:
        self.calls += 1
        return VisionResult(analysis=self.analysis, model="fake", raw=self.analysis.model_dump())


@pytest.fixture
def png_bytes() -> bytes:
    return make_png()
