import json
import sys

import pytest

from finchart_api.config import Settings
from finchart_api.llm.claude_cli import _parse
from finchart_api.llm.factory import build_vision_provider
from finchart_api.llm.gemini import GeminiProvider

from .conftest import make_analysis


def test_default_provider_is_gemini() -> None:
    provider = build_vision_provider(Settings(_env_file=None, gemini_api_key="k"))

    assert isinstance(provider, GeminiProvider)


def test_claude_cli_is_refused_in_production() -> None:
    settings = Settings(_env_file=None, app_env="production", llm_provider="claude_cli")

    with pytest.raises(RuntimeError):
        build_vision_provider(settings)


def test_gemini_path_does_not_need_cli_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, "finchart_api.llm.claude_cli", raising=False)

    build_vision_provider(Settings(_env_file=None, gemini_api_key="k"))

    assert "finchart_api.llm.claude_cli" not in sys.modules


def test_cli_output_parses_structured_and_text_envelopes() -> None:
    data = make_analysis().model_dump()

    structured = _parse(json.dumps({"structured_output": data}).encode())
    text = _parse(json.dumps({"result": f"```json\n{json.dumps(data)}\n```"}).encode())

    assert structured.analysis == text.analysis
