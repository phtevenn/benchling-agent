"""Tests for the Discord bot interface."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from discord.ext import commands

from benchling_agent.clients.benchling import EntryResult
from benchling_agent.clients.claude import ClaudeResponse
from benchling_agent.config import Settings
from benchling_agent.interfaces.discord_bot import MAX_DISCORD_MESSAGE_LENGTH, _truncate, create_bot


def _make_settings() -> Settings:
    return Settings(
        _env_file=None,
        anthropic_api_key="test-key",
        anthropic_model="claude-test",
        benchling_api_url="https://test.benchling.com",
        benchling_api_key="sk_test",
        discord_bot_token="test-token",
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
    def test_bot_has_commands(self, mock_agent_cls):
        bot = create_bot(_make_settings())
        command_names = [cmd.name for cmd in bot.commands]
        assert "write" in command_names
        assert "research" in command_names

    @patch("benchling_agent.interfaces.discord_bot.Agent")
    def test_bot_prefix(self, mock_agent_cls):
        bot = create_bot(_make_settings())
        assert "!" in bot.command_prefix


class TestWriteCommand:
    @patch("benchling_agent.interfaces.discord_bot.Agent")
    @pytest.mark.asyncio
    async def test_write_command_calls_agent(self, mock_agent_cls):
        mock_agent = MagicMock()
        mock_agent_cls.return_value = mock_agent

        write_result = MagicMock()
        write_result.draft = ClaudeResponse(
            content="<h1>PCR</h1>", model="test", input_tokens=50, output_tokens=100
        )
        write_result.entry = EntryResult(
            id="etr_1", name="PCR", folder_id="f1", web_url="https://benchling.com/e/etr_1"
        )
        mock_agent.write_entry.return_value = write_result

        bot = create_bot(_make_settings())
        write_cmd = bot.get_command("write")

        ctx = AsyncMock()
        await write_cmd.callback(ctx, folder_id="f1", prompt="PCR experiment")

        mock_agent.write_entry.assert_called_once_with(prompt="PCR experiment", folder_id="f1")
        assert ctx.send.call_count == 2
        final_msg = ctx.send.call_args_list[1].args[0]
        assert "PCR" in final_msg
        assert "etr_1" in final_msg

    @patch("benchling_agent.interfaces.discord_bot.Agent")
    @pytest.mark.asyncio
    async def test_write_command_handles_error(self, mock_agent_cls):
        mock_agent = MagicMock()
        mock_agent_cls.return_value = mock_agent
        mock_agent.write_entry.side_effect = RuntimeError("API down")

        bot = create_bot(_make_settings())
        write_cmd = bot.get_command("write")

        ctx = AsyncMock()
        await write_cmd.callback(ctx, folder_id="f1", prompt="test")

        final_msg = ctx.send.call_args_list[-1].args[0]
        assert "wrong" in final_msg.lower()


class TestResearchCommand:
    @patch("benchling_agent.interfaces.discord_bot.Agent")
    @pytest.mark.asyncio
    async def test_research_command_calls_agent(self, mock_agent_cls):
        mock_agent = MagicMock()
        mock_agent_cls.return_value = mock_agent

        research_result = MagicMock()
        research_result.response = ClaudeResponse(
            content="CRISPR summary", model="test", input_tokens=30, output_tokens=60
        )
        mock_agent.research.return_value = research_result

        bot = create_bot(_make_settings())
        research_cmd = bot.get_command("research")

        ctx = AsyncMock()
        await research_cmd.callback(ctx, query="CRISPR design")

        mock_agent.research.assert_called_once_with("CRISPR design")
        final_msg = ctx.send.call_args_list[1].args[0]
        assert "CRISPR summary" in final_msg

    @patch("benchling_agent.interfaces.discord_bot.Agent")
    @pytest.mark.asyncio
    async def test_research_command_handles_error(self, mock_agent_cls):
        mock_agent = MagicMock()
        mock_agent_cls.return_value = mock_agent
        mock_agent.research.side_effect = RuntimeError("API down")

        bot = create_bot(_make_settings())
        research_cmd = bot.get_command("research")

        ctx = AsyncMock()
        await research_cmd.callback(ctx, query="test")

        final_msg = ctx.send.call_args_list[-1].args[0]
        assert "wrong" in final_msg.lower()
