import io

import pytest
from PIL import Image, ImageDraw
from pypdf import PdfWriter

from finchart_api.domain.analysis import ChartAnalysis, VisionResult
from finchart_api.domain.articles import (
    ArticleTranslation,
    Paragraph,
    TranslationResult,
    TranslatorError,
)


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


def make_pdf(pages: int = 1, width: int = 600) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=width, height=800)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def make_translation(title: str = "Fed holds rates") -> ArticleTranslation:
    return ArticleTranslation(
        language="en",
        title=title,
        title_ko="연준, 금리 동결",
        source="Reuters",
        published="2026-11-05",
        summary=["연준이 금리를 동결했다.", "연내 인하 가능성을 열어 뒀다."],
        paragraphs=[
            Paragraph(
                kind="paragraph",
                original="The Fed held rates.",
                translated="연준이 금리를 동결했다.",
            ),
            Paragraph(kind="heading", original="Outlook", translated="전망"),
            Paragraph(kind="paragraph", original="  ", translated=""),
        ],
    )


class FakeTranslator:
    def __init__(self) -> None:
        self.translation = make_translation()
        self.calls = 0
        self.error: TranslatorError | None = None

    async def translate(self, pdf: bytes) -> TranslationResult:
        self.calls += 1
        if self.error:
            raise self.error
        return TranslationResult(translation=self.translation, model="fake-translator")


@pytest.fixture
def png_bytes() -> bytes:
    return make_png()
