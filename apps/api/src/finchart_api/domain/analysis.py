from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

ChartType = Literal[
    "line", "candlestick", "bar", "area", "scatter", "pie", "heatmap", "table", "mixed", "other"
]
BboxCoord = Annotated[int, Field(ge=0, le=1000)]


class ChartAnalysis(BaseModel):
    """VLM output for one screenshot. bbox is [ymin, xmin, ymax, xmax] on a 0-1000 grid."""

    bbox: Annotated[list[BboxCoord], Field(min_length=4, max_length=4)]
    title: str
    chart_type: ChartType
    period: str | None
    takeaways: Annotated[list[str], Field(max_length=3)]
    interpretation: str
    caveats: Annotated[list[str], Field(max_length=2)]

    @model_validator(mode="after")
    def _bbox_is_ordered(self) -> "ChartAnalysis":
        ymin, xmin, ymax, xmax = self.bbox
        if ymin >= ymax or xmin >= xmax:
            raise ValueError("bbox must satisfy ymin < ymax and xmin < xmax")
        return self


class VisionResult(BaseModel):
    analysis: ChartAnalysis
    model: str
    raw: dict[str, object]
