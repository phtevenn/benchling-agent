"""Tests for the core agent orchestrator."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from benchling_agent.agent import Action, Agent, ResearchResult, WriteResult
from benchling_agent.clients.benchling import EntryResult
from benchling_agent.clients.claude import ClaudeResponse, EntryDraft
from benchling_agent.config import Settings
from benchling_agent.user_config import UserConfig


def _make_settings() -> Settings:
    return Settings(
        _env_file=None,
        anthropic_api_key="test-key",
        anthropic_model="claude-test",
        benchling_api_url="https://test.benchling.com",
        benchling_api_key="sk_test",
    )


def _stub_entry_draft(
    title: str = "Generated Title", body: str = "<h1>Draft</h1>"
) -> EntryDraft:
    return EntryDraft(
        title=title, body=body,
        model="claude-test", input_tokens=50, output_tokens=100,
    )


def _stub_claude_response(content: str = "Summary") -> ClaudeResponse:
    return ClaudeResponse(content=content, model="claude-test", input_tokens=50, output_tokens=100)


def _stub_entry_result(name: str = "Test Entry") -> EntryResult:
    return EntryResult(
        id="etr_123",
        name=name,
        folder_id="lib_f1",
        web_url="https://test.benchling.com/entry/etr_123",
    )


class TestAction:
    def test_values(self):
        assert Action.WRITE == "write"
        assert Action.RESEARCH == "research"


class TestAgent:
    @patch("benchling_agent.agent.BenchlingBrowser")
    @patch("benchling_agent.agent.BenchlingClient")
    @patch("benchling_agent.agent.ClaudeClient")
    def test_write_entry_with_explicit_name(
        self, mock_claude_cls, mock_benchling_cls, mock_browser_cls
    ):
        mock_claude = MagicMock()
        mock_claude_cls.return_value = mock_claude
        mock_claude.draft_entry.return_value = _stub_entry_draft(body="<h1>PCR</h1>")

        mock_benchling = MagicMock()
        mock_benchling_cls.return_value = mock_benchling
        mock_benchling.create_entry.return_value = _stub_entry_result("PCR Results")

        mock_browser = MagicMock()
        mock_browser_cls.return_value = mock_browser
        mock_browser.is_logged_in.return_value = True
        mock_browser.write_entry_content.return_value = True

        agent = Agent(settings=_make_settings(), user_config=UserConfig())
        result = agent.write_entry(
            prompt="Document PCR experiment",
            folder_id="lib_f1",
            entry_name="PCR Results",
        )

        assert isinstance(result, WriteResult)
        assert result.draft.body == "<h1>PCR</h1>"
        assert result.body_written is True

        today = date.today().strftime("%Y.%m.%d")
        mock_benchling.create_entry.assert_called_once_with(
            name=f"{today} - PCR Results", folder_id="lib_f1"
        )

    @patch("benchling_agent.agent.BenchlingBrowser")
    @patch("benchling_agent.agent.BenchlingClient")
    @patch("benchling_agent.agent.ClaudeClient")
    def test_write_entry_uses_claude_generated_title(
        self, mock_claude_cls, mock_benchling_cls, mock_browser_cls
    ):
        mock_claude = MagicMock()
        mock_claude_cls.return_value = mock_claude
        mock_claude.draft_entry.return_value = _stub_entry_draft(
            title="BRCA1 PCR Amplification Protocol"
        )

        mock_benchling = MagicMock()
        mock_benchling_cls.return_value = mock_benchling
        mock_benchling.create_entry.return_value = _stub_entry_result()

        mock_browser_cls.return_value = MagicMock(is_logged_in=MagicMock(return_value=False))

        agent = Agent(settings=_make_settings(), user_config=UserConfig())
        agent.write_entry(prompt="PCR of BRCA1", folder_id="lib_f1")

        call_kwargs = mock_benchling.create_entry.call_args.kwargs
        today = date.today().strftime("%Y.%m.%d")
        assert call_kwargs["name"] == f"{today} - BRCA1 PCR Amplification Protocol"

    @patch("benchling_agent.agent.BenchlingBrowser")
    @patch("benchling_agent.agent.BenchlingClient")
    @patch("benchling_agent.agent.ClaudeClient")
    def test_write_entry_not_logged_in(
        self, mock_claude_cls, mock_benchling_cls, mock_browser_cls
    ):
        mock_claude = MagicMock()
        mock_claude_cls.return_value = mock_claude
        mock_claude.draft_entry.return_value = _stub_entry_draft()

        mock_benchling = MagicMock()
        mock_benchling_cls.return_value = mock_benchling
        mock_benchling.create_entry.return_value = _stub_entry_result()

        mock_browser = MagicMock()
        mock_browser_cls.return_value = mock_browser
        mock_browser.is_logged_in.return_value = False

        config = UserConfig(default_folder_id="lib_f1")
        agent = Agent(settings=_make_settings(), user_config=config)
        result = agent.write_entry(prompt="test")

        assert result.body_written is False

    @patch("benchling_agent.agent.BenchlingBrowser")
    @patch("benchling_agent.agent.BenchlingClient")
    @patch("benchling_agent.agent.ClaudeClient")
    def test_write_entry_uses_default_folder(
        self, mock_claude_cls, mock_benchling_cls, mock_browser_cls
    ):
        mock_claude = MagicMock()
        mock_claude_cls.return_value = mock_claude
        mock_claude.draft_entry.return_value = _stub_entry_draft()

        mock_benchling = MagicMock()
        mock_benchling_cls.return_value = mock_benchling
        mock_benchling.create_entry.return_value = _stub_entry_result()

        mock_browser_cls.return_value = MagicMock(is_logged_in=MagicMock(return_value=False))

        config = UserConfig(default_folder_id="lib_default")
        agent = Agent(settings=_make_settings(), user_config=config)
        agent.write_entry(prompt="test")

        call_kwargs = mock_benchling.create_entry.call_args.kwargs
        assert call_kwargs["folder_id"] == "lib_default"

    @patch("benchling_agent.agent.BenchlingClient")
    @patch("benchling_agent.agent.ClaudeClient")
    def test_write_entry_no_folder_raises(self, mock_claude_cls, mock_benchling_cls):
        agent = Agent(settings=_make_settings(), user_config=UserConfig())
        with pytest.raises(ValueError, match="No folder specified"):
            agent.write_entry(prompt="test")

    @patch("benchling_agent.agent.BenchlingClient")
    @patch("benchling_agent.agent.ClaudeClient")
    def test_research(self, mock_claude_cls, mock_benchling_cls):
        mock_claude = MagicMock()
        mock_claude_cls.return_value = mock_claude
        mock_claude.research.return_value = _stub_claude_response("CRISPR findings...")

        agent = Agent(settings=_make_settings(), user_config=UserConfig())
        result = agent.research("CRISPR guide RNA design")

        assert isinstance(result, ResearchResult)
        assert result.response.content == "CRISPR findings..."
        mock_claude.research.assert_called_once_with("CRISPR guide RNA design")


class TestConfigureFolder:
    @patch("benchling_agent.user_config.UserConfig.save")
    @patch("benchling_agent.agent.BenchlingClient")
    @patch("benchling_agent.agent.ClaudeClient")
    def test_configure_single_match(self, mock_claude_cls, mock_benchling_cls, mock_save):
        mock_benchling = MagicMock()
        mock_benchling_cls.return_value = mock_benchling
        mock_benchling.list_folders.return_value = [
            {"id": "lib_abc", "name": "Stephen Yu"}
        ]

        config = UserConfig()
        agent = Agent(settings=_make_settings(), user_config=config)

        result = agent.configure_folder("Stephen Yu")
        assert result["id"] == "lib_abc"
        assert result["name"] == "Stephen Yu"
        assert agent.user_config.default_folder_id == "lib_abc"
        assert agent.user_config.default_folder_name == "Stephen Yu"
        mock_save.assert_called_once()

    @patch("benchling_agent.agent.BenchlingClient")
    @patch("benchling_agent.agent.ClaudeClient")
    def test_configure_no_match_raises(self, mock_claude_cls, mock_benchling_cls):
        mock_benchling = MagicMock()
        mock_benchling_cls.return_value = mock_benchling
        mock_benchling.list_folders.return_value = []

        agent = Agent(settings=_make_settings(), user_config=UserConfig())
        with pytest.raises(ValueError, match="No folders found"):
            agent.configure_folder("Nonexistent")

    @patch("benchling_agent.agent.BenchlingClient")
    @patch("benchling_agent.agent.ClaudeClient")
    def test_configure_multiple_matches_raises(self, mock_claude_cls, mock_benchling_cls):
        mock_benchling = MagicMock()
        mock_benchling_cls.return_value = mock_benchling
        mock_benchling.list_folders.return_value = [
            {"id": "lib_1", "name": "Project A"},
            {"id": "lib_2", "name": "Project AB"},
        ]

        agent = Agent(settings=_make_settings(), user_config=UserConfig())
        with pytest.raises(ValueError, match="Multiple folders"):
            agent.configure_folder("Project A")
