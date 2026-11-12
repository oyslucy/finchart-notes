from finchart_api.config import Settings
from finchart_api.domain.articles import Translator
from finchart_api.llm.base import VisionProvider


def build_vision_provider(settings: Settings) -> VisionProvider:
    if settings.llm_provider == "claude_cli":
        if settings.app_env == "production":
            raise RuntimeError("claude_cli provider is for local development only")
        # Imported lazily so production never loads the local-only module.
        from finchart_api.llm.claude_cli import ClaudeCliProvider

        return ClaudeCliProvider()

    from finchart_api.llm.gemini import GeminiProvider

    return GeminiProvider(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        fallback_model=settings.gemini_fallback_model,
    )


def build_translator(settings: Settings) -> Translator | None:
    if not settings.translation_enabled:
        return None
    from finchart_api.llm.claude_api import ClaudeTranslator

    return ClaudeTranslator(
        api_key=settings.anthropic_api_key.get_secret_value(), model=settings.translate_model
    )
