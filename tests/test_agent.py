"""Tests for the core agent orchestrator."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from benchling_agent.agent import Action, Agent, ResearchResult, WriteResult
from benchling_agent.clients.benchling import EntryResult
from benchling_agent.clients.claude import ClaudeResponse
from benchling_agent.config import Settings


def _make_settings() -> Settings:
    return Settings(
        _env_file=None,
        anthropic_api_key="test-key",
        anthropic_model="claude-test",
        benchling_api_url="https://test.benchling.com",
        benchling_api_key="sk_test",
    )


def _stub_claude_response(content: str = "<h1>Draft</h1>") -> ClaudeResponse:
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
    @patch("benchling_agent.agent.BenchlingClient")
    @patch("benchling_agent.agent.ClaudeClient")
    def test_write_entry(self, mock_claude_cls, mock_benchling_cls):
        mock_claude = MagicMock()
        mock_claude_cls.return_value = mock_claude
        mock_claude.draft_entry.return_value = _stub_claude_response("<h1>PCR</h1>")

        mock_benchling = MagicMock()
        mock_benchling_cls.return_value = mock_benchling
        mock_benchling.create_entry.return_value = _stub_entry_result("PCR Results")

        agent = Agent(settings=_make_settings())
        result = agent.write_entry(
            prompt="Document PCR experiment",
            folder_id="lib_f1",
            entry_name="PCR Results",
        )

        assert isinstance(result, WriteResult)
        assert result.draft.content == "<h1>PCR</h1>"
        assert result.entry.name == "PCR Results"

        mock_claude.draft_entry.assert_called_once_with("Document PCR experiment")
        mock_benchling.create_entry.assert_called_once_with(
            name="PCR Results", folder_id="lib_f1"
        )

    @patch("benchling_agent.agent.BenchlingClient")
    @patch("benchling_agent.agent.ClaudeClient")
    def test_write_entry_default_name(self, mock_claude_cls, mock_benchling_cls):
        mock_claude = MagicMock()
        mock_claude_cls.return_value = mock_claude
        mock_claude.draft_entry.return_value = _stub_claude_response()

        mock_benchling = MagicMock()
        mock_benchling_cls.return_value = mock_benchling
        mock_benchling.create_entry.return_value = _stub_entry_result()

        agent = Agent(settings=_make_settings())
        prompt = "A" * 100
        agent.write_entry(prompt=prompt, folder_id="lib_f1")

        call_kwargs = mock_benchling.create_entry.call_args.kwargs
        assert len(call_kwargs["name"]) == 60

    @patch("benchling_agent.agent.BenchlingClient")
    @patch("benchling_agent.agent.ClaudeClient")
    def test_research(self, mock_claude_cls, mock_benchling_cls):
        mock_claude = MagicMock()
        mock_claude_cls.return_value = mock_claude
        mock_claude.research.return_value = _stub_claude_response("CRISPR findings...")

        agent = Agent(settings=_make_settings())
        result = agent.research("CRISPR guide RNA design")

        assert isinstance(result, ResearchResult)
        assert result.response.content == "CRISPR findings..."
        mock_claude.research.assert_called_once_with("CRISPR guide RNA design")
