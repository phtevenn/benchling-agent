"""Tests for the Claude client wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from benchling_agent.clients.claude import (
    DRAFT_ENTRY_PROMPT,
    SYSTEM_PROMPT,
    ClaudeClient,
    ClaudeResponse,
    EntryDraft,
    _parse_title_body,
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


def _mock_anthropic_response(text: str = "# Test", model: str = "claude-test"):
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


class TestEntryDraft:
    def test_fields(self):
        draft = EntryDraft(
            title="My Title", body="# Body",
            model="m", input_tokens=1, output_tokens=2,
        )
        assert draft.title == "My Title"
        assert draft.body == "# Body"


class TestParseTitleBody:
    def test_standard_format(self):
        text = "TITLE: PCR Protocol\nBODY:\n# Protocol\nSome details."
        title, body = _parse_title_body(text)
        assert title == "PCR Protocol"
        assert body == "# Protocol\nSome details."

    def test_strips_quotes_from_title(self):
        text = 'TITLE: "Quoted Title"\nBODY:\nSome content'
        title, body = _parse_title_body(text)
        assert title == "Quoted Title"

    def test_multiline_body(self):
        text = "TITLE: Test\nBODY:\n# Header\nParagraph text"
        title, body = _parse_title_body(text)
        assert title == "Test"
        assert "# Header" in body
        assert "Paragraph text" in body

    def test_fallback_no_separator(self):
        text = "My Title\n# Some content"
        title, body = _parse_title_body(text)
        assert title == "My Title"
        assert body == "# Some content"


class TestClaudeClientChat:
    @patch("benchling_agent.clients.claude.anthropic.Anthropic")
    def test_chat_returns_claude_response(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_anthropic_response(
            "Let's plan your PCR experiment."
        )

        client = ClaudeClient(settings=_make_settings())
        messages = [{"role": "user", "content": "I want to run a PCR experiment"}]
        result = client.chat(messages)

        assert isinstance(result, ClaudeResponse)
        assert result.content == "Let's plan your PCR experiment."
        assert result.input_tokens == 100
        assert result.output_tokens == 200

    @patch("benchling_agent.clients.claude.anthropic.Anthropic")
    def test_chat_passes_messages_to_api(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_anthropic_response("reply")

        client = ClaudeClient(settings=_make_settings())
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "Plan my experiment"},
        ]
        client.chat(messages)

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == SYSTEM_PROMPT
        assert call_kwargs["model"] == "claude-test"
        assert call_kwargs["messages"] == messages

    @patch("benchling_agent.clients.claude.anthropic.Anthropic")
    def test_chat_custom_max_tokens(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_anthropic_response("ok")

        client = ClaudeClient(settings=_make_settings())
        client.chat([{"role": "user", "content": "test"}], max_tokens=2048)

        assert mock_client.messages.create.call_args.kwargs["max_tokens"] == 2048


class TestClaudeClientDraftEntryFromConversation:
    @patch("benchling_agent.clients.claude.anthropic.Anthropic")
    def test_draft_entry_from_conversation(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_anthropic_response(
            "TITLE: PCR Amplification\nBODY:\n"
            "# Purpose\nAmplify target gene.\n\n"
            "# Materials\n- Primers\n\n"
            "# Methods\n- Run thermocycler\n\n"
            "# Results\n"
        )

        client = ClaudeClient(settings=_make_settings())
        messages = [
            {"role": "user", "content": "I want to amplify a target gene via PCR"},
            {"role": "assistant", "content": "What primers will you use?"},
            {"role": "user", "content": "Forward and reverse primers for gene X"},
        ]
        result = client.draft_entry_from_conversation(messages)

        assert isinstance(result, EntryDraft)
        assert result.title == "PCR Amplification"
        assert "# Purpose" in result.body
        assert "# Materials" in result.body
        assert "# Methods" in result.body
        assert "# Results" in result.body

    @patch("benchling_agent.clients.claude.anthropic.Anthropic")
    def test_draft_entry_appends_drafting_prompt(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_anthropic_response(
            "TITLE: T\nBODY:\n# Purpose\n\n# Materials\n\n# Methods\n\n# Results\n"
        )

        client = ClaudeClient(settings=_make_settings())
        conversation = [{"role": "user", "content": "plan my experiment"}]
        client.draft_entry_from_conversation(conversation)

        call_kwargs = mock_client.messages.create.call_args.kwargs
        sent_messages = call_kwargs["messages"]
        # Original message plus the drafting prompt
        assert len(sent_messages) == 2
        assert sent_messages[0] == conversation[0]
        assert sent_messages[1]["content"] == DRAFT_ENTRY_PROMPT

    @patch("benchling_agent.clients.claude.anthropic.Anthropic")
    def test_draft_entry_does_not_mutate_input(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_anthropic_response(
            "TITLE: T\nBODY:\n# Purpose\n\n# Materials\n\n# Methods\n\n# Results\n"
        )

        client = ClaudeClient(settings=_make_settings())
        conversation = [{"role": "user", "content": "plan my experiment"}]
        original_len = len(conversation)
        client.draft_entry_from_conversation(conversation)

        assert len(conversation) == original_len


class TestClaudeClientDraftEntry:
    @patch("benchling_agent.clients.claude.anthropic.Anthropic")
    def test_draft_entry_convenience_wrapper(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_anthropic_response(
            "TITLE: PCR Protocol\nBODY:\n"
            "# Purpose\nTest\n\n# Materials\n- Items\n\n# Methods\n- Steps\n\n# Results\n"
        )

        client = ClaudeClient(settings=_make_settings())
        result = client.draft_entry("PCR experiment")

        assert isinstance(result, EntryDraft)
        assert result.title == "PCR Protocol"

        # Should have sent a user message with the prompt, plus the drafting prompt
        call_kwargs = mock_client.messages.create.call_args.kwargs
        sent_messages = call_kwargs["messages"]
        assert sent_messages[0]["content"] == "PCR experiment"
        assert sent_messages[1]["content"] == DRAFT_ENTRY_PROMPT


class TestClaudeClientResearch:
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
