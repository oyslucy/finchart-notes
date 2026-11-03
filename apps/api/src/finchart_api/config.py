from functools import cached_property, lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "production"] = "development"
    llm_provider: Literal["gemini", "claude_cli"] = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_fallback_model: str | None = "gemini-3.1-flash-lite"
    supabase_url: str = ""
    supabase_anon_key: str = ""
    allowed_emails: str = ""
    rate_limit_per_minute: int = 10
    max_upload_bytes: int = 10 * 1024 * 1024
    web_dist_dir: Path | None = None

    @cached_property
    def allowed_email_set(self) -> frozenset[str]:
        return frozenset(e.strip().lower() for e in self.allowed_emails.split(",") if e.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
