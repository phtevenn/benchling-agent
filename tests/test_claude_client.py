"""Tests for the Claude client wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from benchling_agent.clients.claude import (
    ENTRY_PROMPT_TEMPLATE,
    RESEARCH_PROMPT_TEMPLATE,
    SYSTEM_PROMPT,
    ClaudeClient,
    ClaudeResponse,
)
from benchling_agent.config import Settings


def _make_settings(**overrides) -> Settings:
    defaults = {
        "_env_file": None,
        "anthropic_api_key": "test-key",
        "anthropic_model": "claude-test",
        "benchling_api_url": "",
        "benchling_api_key": "",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _mock_anthropic_response(text: str = "<h1>Test</h1>", model: str = "claude-test"):
    """Build a mock Anthropic Messages response."""
    content_block = MagicMock()
    content_block.text = text

    usage = MagicMock()
    usage.input_tokens = 100
    usage.output_tokens = 200

    response = MagicMock()
    response.content = [content_block]
    response.model = model
    response.usage = usage
    return response


class TestClaudeResponse:
    def test_fields(self):
        resp = ClaudeResponse(content="hello", model="m", input_tokens=1, output_tokens=2)
        assert resp.content == "hello"
        assert resp.model == "m"
        assert resp.input_tokens == 1
        assert resp.output_tokens == 2


class TestClaudeClient:
    @patch("benchling_agent.clients.claude.anthropic.Anthropic")
    def test_draft_entry_calls_api(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_anthropic_response("<h1>PCR</h1>")

        client = ClaudeClient(settings=_make_settings())
        result = client.draft_entry("PCR experiment")

        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == SYSTEM_PROMPT
        assert call_kwargs["model"] == "claude-test"
        assert "PCR experiment" in call_kwargs["messages"][0]["content"]

        assert result.content == "<h1>PCR</h1>"
        assert result.input_tokens == 100
        assert result.output_tokens == 200

    @patch("benchling_agent.clients.claude.anthropic.Anthropic")
    def test_research_calls_api(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_anthropic_response("CRISPR summary")

        client = ClaudeClient(settings=_make_settings())
        result = client.research("CRISPR guide RNA design")

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert "CRISPR guide RNA design" in call_kwargs["messages"][0]["content"]
        assert result.content == "CRISPR summary"

    @patch("benchling_agent.clients.claude.anthropic.Anthropic")
    def test_draft_entry_uses_entry_template(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_anthropic_response()

        client = ClaudeClient(settings=_make_settings())
        client.draft_entry("my experiment")

        user_msg = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        expected = ENTRY_PROMPT_TEMPLATE.format(prompt="my experiment")
        assert user_msg == expected

    @patch("benchling_agent.clients.claude.anthropic.Anthropic")
    def test_research_uses_research_template(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_anthropic_response()

        client = ClaudeClient(settings=_make_settings())
        client.research("protein folding")

        user_msg = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        expected = RESEARCH_PROMPT_TEMPLATE.format(query="protein folding")
        assert user_msg == expected

    @patch("benchling_agent.clients.claude.anthropic.Anthropic")
    def test_custom_max_tokens(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_anthropic_response()

        client = ClaudeClient(settings=_make_settings())
        client.draft_entry("test", max_tokens=1024)

        assert mock_client.messages.create.call_args.kwargs["max_tokens"] == 1024
