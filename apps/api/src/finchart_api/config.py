from functools import cached_property, lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
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
    # Starter boards for new accounts, comma-separated, in display order.
    default_boards: str = "반도체,IT,2차전지,바이오,금융"
    web_dist_dir: Path | None = None
    # Used to build links back to the web app (Telegram replies).
    public_base_url: str = "https://finchart-notes.duckdns.org"
    # SecretStr keeps tokens out of reprs and logs.
    telegram_bot_token: SecretStr = SecretStr("")
    telegram_bot_username: str = ""
    telegram_webhook_secret: SecretStr = SecretStr("")
    # "webhook" in production; "polling" for local development without a public URL.
    telegram_mode: Literal["webhook", "polling", "off"] = "webhook"

    @cached_property
    def allowed_username_set(self) -> frozenset[str]:
        return frozenset(u.strip().lower() for u in self.allowed_usernames.split(",") if u.strip())

    @property
    def default_board_names(self) -> list[str]:
        return [n.strip() for n in self.default_boards.split(",") if n.strip()]

    def is_username_allowed(self, username: str) -> bool:
        return not self.allowed_username_set or username in self.allowed_username_set

    @property
    def telegram_enabled(self) -> bool:
        return bool(
            self.telegram_mode != "off"
            and self.telegram_bot_token.get_secret_value()
            and self.telegram_bot_username
        )

    @property
    def secure_cookies(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
