import json
from collections.abc import Sequence
from types import SimpleNamespace
from typing import Any

import pytest

from finchart_api.llm.base import VisionProviderError
from finchart_api.llm.gemini import GeminiProvider

from .conftest import make_analysis


class StatusError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"status {status_code}")
        self.status_code = status_code


class FakeInteractions:
    def __init__(self, outcomes: Sequence[Exception | str]) -> None:
        self.outcomes = list(outcomes)
        self.models: list[str] = []

    async def create(self, **body: Any) -> Any:
        self.models.append(body["model"])
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(output_text=outcome)


def _provider(fake: FakeInteractions, delays: list[float]) -> GeminiProvider:
    async def sleep(seconds: float) -> None:
        delays.append(seconds)

    return GeminiProvider("k", "primary", "fallback", interactions=fake, sleep=sleep)


VALID = json.dumps(make_analysis().model_dump(), ensure_ascii=False)


async def test_success_on_first_try(png_bytes: bytes) -> None:
    delays: list[float] = []
    fake = FakeInteractions([VALID])

    result = await _provider(fake, delays).analyze(png_bytes)

    assert result.model == "primary"
    assert result.analysis.title == "KOSPI 일봉"
    assert delays == []


async def test_retries_with_backoff_then_falls_back(png_bytes: bytes) -> None:
    fake = FakeInteractions([StatusError(429)] * 4 + [VALID])
    delays: list[float] = []

    result = await _provider(fake, delays).analyze(png_bytes)

    assert result.model == "fallback"
    assert fake.models == ["primary"] * 4 + ["fallback"]
    assert delays == [1.0, 2.0, 4.0]


async def test_server_error_recovers_within_retries(png_bytes: bytes) -> None:
    delays: list[float] = []
    fake = FakeInteractions([StatusError(503), VALID])

    result = await _provider(fake, delays).analyze(png_bytes)

    assert result.model == "primary"
    assert delays == [1.0]


async def test_client_error_is_not_retried(png_bytes: bytes) -> None:
    delays: list[float] = []
    fake = FakeInteractions([StatusError(400)])

    with pytest.raises(VisionProviderError):
        await _provider(fake, delays).analyze(png_bytes)
    assert fake.models == ["primary"]


async def test_invalid_json_raises(png_bytes: bytes) -> None:
    delays: list[float] = []
    fake = FakeInteractions(["{not json"])

    with pytest.raises(VisionProviderError):
        await _provider(fake, delays).analyze(png_bytes)


async def test_all_models_exhausted_raises(png_bytes: bytes) -> None:
    delays: list[float] = []
    fake = FakeInteractions([StatusError(500)] * 8)

    with pytest.raises(VisionProviderError):
        await _provider(fake, delays).analyze(png_bytes)
    assert fake.models == ["primary"] * 4 + ["fallback"] * 4
