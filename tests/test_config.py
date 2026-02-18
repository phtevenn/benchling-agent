"""Tests for configuration module."""

from benchling_agent.config import Settings


class TestSettings:
    def test_defaults(self):
        settings = Settings(
            _env_file=None,
            anthropic_api_key="",
            benchling_api_url="",
            benchling_api_key="",
        )
        assert settings.anthropic_model == "claude-sonnet-4-20250514"
        assert settings.discord_bot_token == ""

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("BENCHLING_API_URL", "https://test.benchling.com")
        monkeypatch.setenv("BENCHLING_API_KEY", "sk_test")
        settings = Settings(_env_file=None)
        assert settings.anthropic_api_key == "test-key"
        assert settings.benchling_api_url == "https://test.benchling.com"
        assert settings.benchling_api_key == "sk_test"
