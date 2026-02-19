"""Tests for the Discord bot interface (slash commands + on_message)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from discord.ext import commands

from benchling_agent.clients.benchling import EntryResult
from benchling_agent.clients.claude import EntryDraft
from benchling_agent.config import Settings
from benchling_agent.interfaces.discord_bot import (
    MAX_DISCORD_MESSAGE_LENGTH,
    _truncate,
    create_bot,
)
from benchling_agent.session import ConversationSession, SessionState


def _make_settings() -> Settings:
    return Settings(
        _env_file=None,
        anthropic_api_key="test-key",
        anthropic_model="claude-test",
        benchling_api_url="https://test.benchling.com",
        benchling_api_key="sk_test",
        discord_bot_token="test-token",
    )


def _stub_draft(title: str = "PCR Protocol", body: str = "# Purpose\nTest") -> EntryDraft:
    return EntryDraft(
        title=title, body=body, model="claude-test", input_tokens=50, output_tokens=100
    )


def _stub_entry_result() -> EntryResult:
    return EntryResult(
        id="etr_123",
        name="PCR Protocol",
        folder_id="lib_f1",
        web_url="https://test.benchling.com/entry/etr_123",
    )


class TestTruncate:
    def test_short_text_unchanged(self):
        assert _truncate("hello") == "hello"

    def test_long_text_truncated(self):
        text = "a" * 2500
        result = _truncate(text)
        assert len(result) == MAX_DISCORD_MESSAGE_LENGTH
        assert result.endswith("...")

    def test_exact_limit(self):
        text = "a" * MAX_DISCORD_MESSAGE_LENGTH
        assert _truncate(text) == text

    def test_custom_limit(self):
        result = _truncate("hello world", limit=8)
        assert result == "hello..."
        assert len(result) == 8


class TestCreateBot:
    @patch("benchling_agent.interfaces.discord_bot.Agent")
    def test_returns_bot_instance(self, mock_agent_cls):
        bot = create_bot(_make_settings())
        assert isinstance(bot, commands.Bot)

    @patch("benchling_agent.interfaces.discord_bot.Agent")
    def test_bot_has_slash_commands(self, mock_agent_cls):
        bot = create_bot(_make_settings())
        slash_names = [cmd.name for cmd in bot.tree.get_commands()]
        assert "configure" in slash_names
        assert "reset" in slash_names
        assert "finalize" in slash_names
        assert "confirm" in slash_names
        assert "cancel" in slash_names

    @patch("benchling_agent.interfaces.discord_bot.Agent")
    def test_bot_prefix(self, mock_agent_cls):
        bot = create_bot(_make_settings())
        assert "!" in bot.command_prefix


class TestResetCommand:
    @patch("benchling_agent.interfaces.discord_bot.Agent")
    @pytest.mark.asyncio
    async def test_reset_clears_session(self, mock_agent_cls):
        bot = create_bot(_make_settings())
        cmd = next(c for c in bot.tree.get_commands() if c.name == "reset")

        interaction = AsyncMock()
        interaction.channel_id = 42

        await cmd.callback(interaction)

        interaction.response.send_message.assert_called_once()
        msg = interaction.response.send_message.call_args.args[0]
        assert "cleared" in msg.lower()


class TestConfigureCommand:
    @patch("benchling_agent.interfaces.discord_bot.Agent")
    @pytest.mark.asyncio
    async def test_configure_success(self, mock_agent_cls):
        mock_agent = MagicMock()
        mock_agent_cls.return_value = mock_agent
        mock_agent.configure_folder.return_value = {"id": "lib_abc", "name": "Stephen Yu"}

        bot = create_bot(_make_settings())
        cmd = next(c for c in bot.tree.get_commands() if c.name == "configure")

        interaction = AsyncMock()
        await cmd.callback(interaction, folder="Stephen Yu")

        mock_agent.configure_folder.assert_called_once_with("Stephen Yu")
        msg = interaction.response.send_message.call_args.args[0]
        assert "Stephen Yu" in msg
        assert "lib_abc" in msg

    @patch("benchling_agent.interfaces.discord_bot.Agent")
    @pytest.mark.asyncio
    async def test_configure_no_match(self, mock_agent_cls):
        mock_agent = MagicMock()
        mock_agent_cls.return_value = mock_agent
        mock_agent.configure_folder.side_effect = ValueError("No folders found")

        bot = create_bot(_make_settings())
        cmd = next(c for c in bot.tree.get_commands() if c.name == "configure")

        interaction = AsyncMock()
        await cmd.callback(interaction, folder="Nope")

        msg = interaction.response.send_message.call_args.args[0]
        assert "No folders found" in msg


class TestFinalizeCommand:
    @patch("benchling_agent.interfaces.discord_bot.SessionStore")
    @patch("benchling_agent.interfaces.discord_bot.Agent")
    @pytest.mark.asyncio
    async def test_finalize_no_conversation(self, mock_agent_cls, mock_store_cls):
        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store
        mock_store.get.return_value = None

        bot = create_bot(_make_settings())
        cmd = next(c for c in bot.tree.get_commands() if c.name == "finalize")

        interaction = AsyncMock()
        interaction.channel_id = 42
        await cmd.callback(interaction)

        interaction.response.defer.assert_called_once()
        msg = interaction.followup.send.call_args.args[0]
        assert "no conversation" in msg.lower()

    @patch("benchling_agent.interfaces.discord_bot.SessionStore")
    @patch("benchling_agent.interfaces.discord_bot.Agent")
    @pytest.mark.asyncio
    async def test_finalize_with_conversation(self, mock_agent_cls, mock_store_cls):
        mock_agent = MagicMock()
        mock_agent_cls.return_value = mock_agent
        draft = _stub_draft()
        mock_agent.propose_entry.return_value = draft

        session = ConversationSession(
            channel_id=42,
            messages=[{"role": "user", "content": "plan PCR"}],
        )
        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store
        mock_store.get.return_value = session

        bot = create_bot(_make_settings())
        cmd = next(c for c in bot.tree.get_commands() if c.name == "finalize")

        interaction = AsyncMock()
        interaction.channel_id = 42
        await cmd.callback(interaction)

        mock_agent.propose_entry.assert_called_once_with(session.messages)
        mock_store.set_pending_draft.assert_called_once_with(42, draft)
        msg = interaction.followup.send.call_args.args[0]
        assert "PCR Protocol" in msg


class TestConfirmCommand:
    @patch("benchling_agent.interfaces.discord_bot.SessionStore")
    @patch("benchling_agent.interfaces.discord_bot.Agent")
    @pytest.mark.asyncio
    async def test_confirm_no_pending(self, mock_agent_cls, mock_store_cls):
        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store
        mock_store.get.return_value = None

        bot = create_bot(_make_settings())
        cmd = next(c for c in bot.tree.get_commands() if c.name == "confirm")

        interaction = AsyncMock()
        interaction.channel_id = 42
        await cmd.callback(interaction)

        interaction.response.defer.assert_called_once()
        msg = interaction.followup.send.call_args.args[0]
        assert "no pending" in msg.lower()

    @patch("benchling_agent.interfaces.discord_bot.SessionStore")
    @patch("benchling_agent.interfaces.discord_bot.Agent")
    @pytest.mark.asyncio
    async def test_confirm_creates_entry(self, mock_agent_cls, mock_store_cls):
        mock_agent = MagicMock()
        mock_agent_cls.return_value = mock_agent

        draft = _stub_draft()
        entry_result = MagicMock()
        entry_result.entry = _stub_entry_result()
        mock_agent.create_entry_from_draft.return_value = entry_result

        session = ConversationSession(channel_id=42, pending_draft=draft)
        session.state = SessionState.PENDING_APPROVAL
        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store
        mock_store.get.return_value = session

        bot = create_bot(_make_settings())
        cmd = next(c for c in bot.tree.get_commands() if c.name == "confirm")

        interaction = AsyncMock()
        interaction.channel_id = 42
        await cmd.callback(interaction)

        mock_agent.create_entry_from_draft.assert_called_once_with(draft)
        mock_store.clear_pending_draft.assert_called_once_with(42)


class TestCancelCommand:
    @patch("benchling_agent.interfaces.discord_bot.SessionStore")
    @patch("benchling_agent.interfaces.discord_bot.Agent")
    @pytest.mark.asyncio
    async def test_cancel_no_pending(self, mock_agent_cls, mock_store_cls):
        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store
        mock_store.get.return_value = None

        bot = create_bot(_make_settings())
        cmd = next(c for c in bot.tree.get_commands() if c.name == "cancel")

        interaction = AsyncMock()
        interaction.channel_id = 42
        await cmd.callback(interaction)

        msg = interaction.response.send_message.call_args.args[0]
        assert "no pending" in msg.lower()

    @patch("benchling_agent.interfaces.discord_bot.SessionStore")
    @patch("benchling_agent.interfaces.discord_bot.Agent")
    @pytest.mark.asyncio
    async def test_cancel_clears_draft(self, mock_agent_cls, mock_store_cls):
        draft = _stub_draft()
        session = ConversationSession(channel_id=42, pending_draft=draft)
        session.state = SessionState.PENDING_APPROVAL
        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store
        mock_store.get.return_value = session

        bot = create_bot(_make_settings())
        cmd = next(c for c in bot.tree.get_commands() if c.name == "cancel")

        interaction = AsyncMock()
        interaction.channel_id = 42
        await cmd.callback(interaction)

        mock_store.clear_pending_draft.assert_called_once_with(42)
        msg = interaction.response.send_message.call_args.args[0]
        assert "cancelled" in msg.lower()


class TestOnMessage:
    @patch("benchling_agent.interfaces.discord_bot.SessionStore")
    @patch("benchling_agent.interfaces.discord_bot.Agent")
    @pytest.mark.asyncio
    async def test_ignores_bot_messages(self, mock_agent_cls, mock_store_cls):
        bot = create_bot(_make_settings())

        message = AsyncMock()
        message.author.bot = True

        # Trigger on_message
        for listener in bot.extra_events.get("on_message", []):
            await listener(message)
        # The default on_message from commands.Bot is replaced, so we call it directly
        # Just verify no crash and no store interaction
        mock_store_cls.return_value.get_or_create.assert_not_called()

    @patch("benchling_agent.interfaces.discord_bot.SessionStore")
    @patch("benchling_agent.interfaces.discord_bot.Agent")
    @pytest.mark.asyncio
    async def test_ignores_slash_commands(self, mock_agent_cls, mock_store_cls):
        bot = create_bot(_make_settings())

        message = AsyncMock()
        message.author.bot = False
        message.content = "/finalize"

        for listener in bot.extra_events.get("on_message", []):
            await listener(message)

        mock_store_cls.return_value.get_or_create.assert_not_called()
