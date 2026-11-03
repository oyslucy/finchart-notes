import asyncio
import base64
import json
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, cast

from pydantic import ValidationError

from finchart_api.domain.analysis import ChartAnalysis, VisionResult
from finchart_api.imaging import detect_mime
from finchart_api.llm.base import VisionProviderError
from finchart_api.llm.prompt import build_prompt, response_schema

MAX_RETRIES = 3
BASE_DELAY_S = 1.0


class _Interactions(Protocol):
    async def create(self, **body: Any) -> Any: ...


class RetryableError(VisionProviderError):
    pass


def _status_of(exc: Exception) -> int | None:
    for attr in ("status_code", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    return None


def _is_retryable(exc: Exception) -> bool:
    status = _status_of(exc)
    # No status means a transport failure (timeout, reset), which is worth retrying.
    return status is None or status == 429 or status >= 500


class GeminiProvider:
    def __init__(
        self,
        api_key: str,
        model: str,
        fallback_model: str | None,
        *,
        interactions: _Interactions | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if interactions is None:
            from google import genai

            self._client = genai.Client(api_key=api_key)
            interactions = cast(_Interactions, self._client.aio.interactions)
        self._interactions: _Interactions = interactions
        self._models = [m for m in (model, fallback_model) if m]
        self._sleep = sleep

    async def analyze(self, image_bytes: bytes) -> VisionResult:
        body_input = [
            {"type": "text", "text": build_prompt()},
            {
                "type": "image",
                "data": base64.b64encode(image_bytes).decode("ascii"),
                "mime_type": detect_mime(image_bytes),
            },
        ]
        last_error: Exception | None = None
        for model in self._models:
            try:
                return await self._call_with_retries(model, body_input)
            except RetryableError as exc:
                last_error = exc
        raise VisionProviderError("all Gemini models failed") from last_error

    async def _call_with_retries(
        self, model: str, body_input: list[dict[str, str]]
    ) -> VisionResult:
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await self._interactions.create(
                    model=model,
                    input=body_input,
                    response_format={
                        "type": "text",
                        "mime_type": "application/json",
                        "schema": response_schema(),
                    },
                )
            except Exception as exc:
                if not _is_retryable(exc):
                    raise VisionProviderError(f"Gemini request failed: {exc}") from exc
                if attempt == MAX_RETRIES:
                    raise RetryableError(f"{model} kept failing") from exc
                await self._sleep(BASE_DELAY_S * 2**attempt)
                continue
            return _parse(model, response.output_text)
        raise AssertionError("unreachable")


def _parse(model: str, text: str | None) -> VisionResult:
    try:
        raw = json.loads(text or "")
        analysis = ChartAnalysis.model_validate(raw)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise VisionProviderError(f"invalid structured output from {model}") from exc
    return VisionResult(analysis=analysis, model=model, raw=raw)
