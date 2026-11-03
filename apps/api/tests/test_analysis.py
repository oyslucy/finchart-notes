import pytest
from pydantic import ValidationError

from finchart_api.domain.analysis import ChartAnalysis

from .conftest import make_analysis


def test_rejects_unordered_bbox() -> None:
    with pytest.raises(ValidationError):
        make_analysis([500, 100, 400, 600])


def test_rejects_out_of_range_bbox() -> None:
    with pytest.raises(ValidationError):
        make_analysis([0, 0, 1001, 500])


def test_rejects_too_many_takeaways() -> None:
    data = make_analysis().model_dump()
    data["takeaways"] = ["a", "b", "c", "d"]
    with pytest.raises(ValidationError):
        ChartAnalysis.model_validate(data)
