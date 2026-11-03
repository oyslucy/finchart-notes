"""Local development provider that shells out to the `claude` CLI. Never loaded in production."""

import asyncio
import json
import tempfile
from pathlib import Path

from pydantic import ValidationError

from finchart_api.domain.analysis import ChartAnalysis, VisionResult
from finchart_api.imaging import detect_mime
from finchart_api.llm.base import VisionProviderError
from finchart_api.llm.prompt import build_prompt, response_schema

_SUFFIX_BY_MIME = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
TIMEOUT_S = 180


class ClaudeCliProvider:
    def __init__(self, executable: str = "claude") -> None:
        self._executable = executable

    async def analyze(self, image_bytes: bytes) -> VisionResult:
        suffix = _SUFFIX_BY_MIME[detect_mime(image_bytes)]
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / f"screenshot{suffix}"
            image_path.write_bytes(image_bytes)
            stdout = await self._run(image_path)
        return _parse(stdout)

    async def _run(self, image_path: Path) -> bytes:
        prompt = f"{build_prompt()}\n\n분석할 이미지 파일: {image_path}"
        proc = await asyncio.create_subprocess_exec(
            self._executable,
            "-p",
            prompt,
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(response_schema()),
            "--allowedTools",
            "Read",
            "--add-dir",
            str(image_path.parent),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), TIMEOUT_S)
        except TimeoutError as exc:
            proc.kill()
            raise VisionProviderError("cli provider timed out") from exc
        if proc.returncode != 0:
            raise VisionProviderError(f"cli provider failed: {stderr.decode(errors='replace')}")
        return stdout


def _parse(stdout: bytes) -> VisionResult:
    try:
        envelope = json.loads(stdout)
        raw = envelope.get("structured_output") or _json_from_text(envelope["result"])
        analysis = ChartAnalysis.model_validate(raw)
    except (json.JSONDecodeError, KeyError, ValidationError) as exc:
        raise VisionProviderError("invalid output from cli provider") from exc
    return VisionResult(analysis=analysis, model="claude-cli", raw=raw)


def _json_from_text(text: str) -> dict[str, object]:
    start, end = text.find("{"), text.rfind("}")
    parsed: dict[str, object] = json.loads(text[start : end + 1])
    return parsed
