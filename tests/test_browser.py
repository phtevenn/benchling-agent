"""Tests for the browser automation client."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from benchling_agent.clients.browser import (
    BODY_SELECTOR,
    STORAGE_DIR,
    STORAGE_STATE_PATH,
    BenchlingBrowser,
)
from benchling_agent.config import Settings


def _make_settings() -> Settings:
    return Settings(
        _env_file=None,
        anthropic_api_key="",
        benchling_api_url="https://test.benchling.com",
        benchling_api_key="",
    )


def _mock_playwright():
    """Set up a mock playwright -> browser -> context -> page chain."""
    mock_pw = MagicMock()
    mock_pw_instance = MagicMock()
    mock_pw.return_value.start.return_value = mock_pw_instance
    mock_browser = MagicMock()
    mock_pw_instance.chromium.launch.return_value = mock_browser
    mock_context = MagicMock()
    mock_browser.new_context.return_value = mock_context
    mock_page = MagicMock()
    mock_context.pages = [mock_page]
    return mock_pw, mock_pw_instance, mock_browser, mock_context, mock_page


class TestBenchlingBrowser:
    def test_init(self):
        browser = BenchlingBrowser(settings=_make_settings())
        assert browser.headless is False
        assert browser._context is None

    def test_storage_paths(self):
        assert STORAGE_DIR == Path.home() / ".benchling-agent"
        assert STORAGE_STATE_PATH == Path.home() / ".benchling-agent" / "browser-state.json"

    @patch("playwright.sync_api.sync_playwright")
    def test_ensure_context_launches_browser(self, mock_pw):
        _, mock_pw_instance, mock_browser, mock_context, _ = _mock_playwright()
        mock_pw.return_value.start.return_value = mock_pw_instance

        browser = BenchlingBrowser(settings=_make_settings())
        ctx = browser._ensure_context()

        assert ctx is mock_context
        mock_pw_instance.chromium.launch.assert_called_once()
        mock_browser.new_context.assert_called_once()

    @patch("playwright.sync_api.sync_playwright")
    def test_close(self, mock_pw):
        _, mock_pw_instance, mock_browser, mock_context, _ = _mock_playwright()
        mock_pw.return_value.start.return_value = mock_pw_instance

        browser = BenchlingBrowser(settings=_make_settings())
        browser._ensure_context()
        browser.close()

        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()
        mock_pw_instance.stop.assert_called_once()
        assert browser._context is None

    @patch("benchling_agent.clients.browser.STORAGE_STATE_PATH")
    @patch("playwright.sync_api.sync_playwright")
    def test_is_logged_in_true(self, mock_pw, mock_path):
        _, mock_pw_instance, _, mock_context, mock_page = _mock_playwright()
        mock_pw.return_value.start.return_value = mock_pw_instance
        mock_page.url = "https://test.benchling.com/gatebio/f/something"
        mock_path.exists.return_value = True

        browser = BenchlingBrowser(settings=_make_settings())
        assert browser.is_logged_in() is True

    @patch("benchling_agent.clients.browser.STORAGE_STATE_PATH")
    @patch("playwright.sync_api.sync_playwright")
    def test_is_logged_in_false_no_state(self, mock_pw, mock_path):
        mock_path.exists.return_value = False

        browser = BenchlingBrowser(settings=_make_settings())
        assert browser.is_logged_in() is False

    @patch("benchling_agent.clients.browser.STORAGE_STATE_PATH")
    @patch("benchling_agent.clients.browser.parse_content")
    @patch("playwright.sync_api.sync_playwright")
    def test_write_entry_content(self, mock_pw, mock_parse, mock_path):
        _, mock_pw_instance, _, mock_context, mock_page = _mock_playwright()
        mock_pw.return_value.start.return_value = mock_pw_instance
        mock_page.url = "https://test.benchling.com/entry/etr_123/edit"
        mock_parse.return_value = []
        mock_path.exists.return_value = True

        mock_editor = MagicMock()
        mock_page.locator.return_value.first = mock_editor

        browser = BenchlingBrowser(settings=_make_settings())
        result = browser.write_entry_content(
            "https://test.benchling.com/entry/etr_123/edit",
            "# Heading\nSome text",
        )

        assert result is True
        mock_page.goto.assert_called_once()
        mock_parse.assert_called_once_with("# Heading\nSome text")

    @patch("benchling_agent.clients.browser.STORAGE_STATE_PATH")
    @patch("playwright.sync_api.sync_playwright")
    def test_write_entry_content_redirected(self, mock_pw, mock_path):
        _, mock_pw_instance, _, mock_context, mock_page = _mock_playwright()
        mock_pw.return_value.start.return_value = mock_pw_instance
        mock_page.url = "https://sso.example.com/login"
        mock_path.exists.return_value = True

        browser = BenchlingBrowser(settings=_make_settings())
        result = browser.write_entry_content(
            "https://test.benchling.com/entry/etr_123/edit",
            "# Test",
        )

        assert result is False

    def test_body_selector_excludes_hidden(self):
        assert "hiddenFocusEditable" in BODY_SELECTOR
        assert "mediocre-titleEditor" in BODY_SELECTOR
