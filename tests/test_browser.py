"""Tests for the browser automation client."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from benchling_agent.clients.browser import SESSION_DIR, BenchlingBrowser
from benchling_agent.config import Settings


def _make_settings() -> Settings:
    return Settings(
        _env_file=None,
        anthropic_api_key="",
        benchling_api_url="https://test.benchling.com",
        benchling_api_key="",
    )


class TestBenchlingBrowser:
    def test_init(self):
        browser = BenchlingBrowser(settings=_make_settings())
        assert browser.headless is False
        assert browser._context is None

    def test_session_dir_path(self):
        assert SESSION_DIR == Path.home() / ".benchling-agent" / "browser-session"

    @patch("playwright.sync_api.sync_playwright")
    def test_ensure_context_launches_browser(self, mock_pw):
        mock_pw_instance = MagicMock()
        mock_pw.return_value.start.return_value = mock_pw_instance
        mock_context = MagicMock()
        mock_pw_instance.chromium.launch_persistent_context.return_value = mock_context

        browser = BenchlingBrowser(settings=_make_settings())
        ctx = browser._ensure_context()

        assert ctx is mock_context
        mock_pw_instance.chromium.launch_persistent_context.assert_called_once()

    @patch("playwright.sync_api.sync_playwright")
    def test_close(self, mock_pw):
        mock_pw_instance = MagicMock()
        mock_pw.return_value.start.return_value = mock_pw_instance
        mock_context = MagicMock()
        mock_pw_instance.chromium.launch_persistent_context.return_value = mock_context

        browser = BenchlingBrowser(settings=_make_settings())
        browser._ensure_context()
        browser.close()

        mock_context.close.assert_called_once()
        mock_pw_instance.stop.assert_called_once()
        assert browser._context is None

    @patch("playwright.sync_api.sync_playwright")
    def test_is_logged_in_true(self, mock_pw):
        mock_pw_instance = MagicMock()
        mock_pw.return_value.start.return_value = mock_pw_instance
        mock_context = MagicMock()
        mock_pw_instance.chromium.launch_persistent_context.return_value = mock_context

        mock_page = MagicMock()
        mock_page.url = "https://test.benchling.com/gatebio/f/something"
        mock_context.pages = [mock_page]

        browser = BenchlingBrowser(settings=_make_settings())
        assert browser.is_logged_in() is True
        mock_page.goto.assert_called_once()

    @patch("playwright.sync_api.sync_playwright")
    def test_is_logged_in_false(self, mock_pw):
        mock_pw_instance = MagicMock()
        mock_pw.return_value.start.return_value = mock_pw_instance
        mock_context = MagicMock()
        mock_pw_instance.chromium.launch_persistent_context.return_value = mock_context

        mock_page = MagicMock()
        mock_page.url = "https://sso.example.com/login"
        mock_context.pages = [mock_page]

        browser = BenchlingBrowser(settings=_make_settings())
        assert browser.is_logged_in() is False

    @patch("playwright.sync_api.sync_playwright")
    def test_write_entry_content(self, mock_pw):
        mock_pw_instance = MagicMock()
        mock_pw.return_value.start.return_value = mock_pw_instance
        mock_context = MagicMock()
        mock_pw_instance.chromium.launch_persistent_context.return_value = mock_context

        mock_page = MagicMock()
        mock_context.pages = [mock_page]
        mock_editor = MagicMock()
        mock_page.locator.return_value.first = mock_editor

        browser = BenchlingBrowser(settings=_make_settings())
        result = browser.write_entry_content(
            "https://test.benchling.com/entry/etr_123/edit",
            "<h1>Test</h1>",
        )

        assert result is True
        mock_page.goto.assert_called_once()
        mock_page.evaluate.assert_called_once()
        call_args = mock_page.evaluate.call_args
        assert "<h1>Test</h1>" in call_args.args
