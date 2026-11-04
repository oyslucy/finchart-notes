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
    data_dir: Path = Path("data")
    backup_bucket: str = "finchart-backups"
    # Optional allow-list; when empty anyone may sign up.
    allowed_usernames: str = ""
    rate_limit_per_minute: int = 10
    # Gemini's free quota is shared by every user, so each account gets a daily share.
    daily_analyses_per_user: int = 30
    login_attempts_per_minute: int = 10
    signups_per_ip_per_hour: int = 5
    max_upload_bytes: int = 10 * 1024 * 1024
    web_dist_dir: Path | None = None

    @cached_property
    def allowed_username_set(self) -> frozenset[str]:
        return frozenset(u.strip().lower() for u in self.allowed_usernames.split(",") if u.strip())

    def is_username_allowed(self, username: str) -> bool:
        return not self.allowed_username_set or username in self.allowed_username_set

    @property
    def secure_cookies(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
