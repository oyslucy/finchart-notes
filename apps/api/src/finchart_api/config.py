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
    allowed_usernames: str = ""
    allowed_emails: str = ""
    # Usernames are stored in Supabase as <username>@<this domain>; must match the web app.
    username_email_domain: str = "users.finchart-notes.duckdns.org"
    rate_limit_per_minute: int = 10
    max_upload_bytes: int = 10 * 1024 * 1024
    web_dist_dir: Path | None = None

    @cached_property
    def allowed_email_set(self) -> frozenset[str]:
        return _csv_set(self.allowed_emails)

    @cached_property
    def allowed_username_set(self) -> frozenset[str]:
        return _csv_set(self.allowed_usernames)

    def is_allowed(self, email: str) -> bool:
        local, _, domain = email.partition("@")
        if domain == self.username_email_domain and local in self.allowed_username_set:
            return True
        return email in self.allowed_email_set


def _csv_set(raw: str) -> frozenset[str]:
    return frozenset(item.strip().lower() for item in raw.split(",") if item.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
