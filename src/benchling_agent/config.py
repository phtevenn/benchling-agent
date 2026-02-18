"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    benchling_api_url: str = ""
    benchling_api_key: str = ""

    discord_bot_token: str = ""


def get_settings() -> Settings:
    return Settings()
