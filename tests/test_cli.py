"""Tests for the CLI interface."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from benchling_agent.clients.benchling import EntryResult
from benchling_agent.clients.claude import ClaudeResponse
from benchling_agent.interfaces.cli import cli


def _stub_write_result():
    result = MagicMock()
    result.draft = ClaudeResponse(
        content="<h1>PCR</h1>", model="claude-test", input_tokens=50, output_tokens=100
    )
    result.entry = EntryResult(
        id="etr_123",
        name="PCR Results",
        folder_id="lib_f1",
        web_url="https://test.benchling.com/entry/etr_123",
    )
    return result


def _stub_research_result():
    result = MagicMock()
    result.response = ClaudeResponse(
        content="CRISPR summary here.", model="claude-test", input_tokens=40, output_tokens=80
    )
    return result


class TestCliHelp:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Benchling Agent" in result.output

    def test_write_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["write", "--help"])
        assert result.exit_code == 0
        assert "--prompt" in result.output
        assert "--folder-id" in result.output

    def test_research_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["research", "--help"])
        assert result.exit_code == 0
        assert "--query" in result.output


class TestWriteCommand:
    def test_requires_prompt(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["write", "--folder-id", "lib_f1"])
        assert result.exit_code != 0

    def test_requires_folder_id(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["write", "--prompt", "test"])
        assert result.exit_code != 0

    @patch("benchling_agent.interfaces.cli._make_agent")
    def test_write_success(self, mock_make_agent):
        mock_agent = MagicMock()
        mock_make_agent.return_value = mock_agent
        mock_agent.write_entry.return_value = _stub_write_result()

        runner = CliRunner()
        result = runner.invoke(
            cli, ["write", "--prompt", "PCR experiment", "--folder-id", "lib_f1"]
        )

        assert result.exit_code == 0
        assert "Entry created: PCR Results" in result.output
        assert "etr_123" in result.output
        assert "<h1>PCR</h1>" in result.output
        mock_agent.write_entry.assert_called_once_with(
            prompt="PCR experiment", folder_id="lib_f1", entry_name=None
        )

    @patch("benchling_agent.interfaces.cli._make_agent")
    def test_write_with_name(self, mock_make_agent):
        mock_agent = MagicMock()
        mock_make_agent.return_value = mock_agent
        mock_agent.write_entry.return_value = _stub_write_result()

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["write", "-p", "PCR experiment", "-f", "lib_f1", "-n", "My Entry"],
        )

        assert result.exit_code == 0
        mock_agent.write_entry.assert_called_once_with(
            prompt="PCR experiment", folder_id="lib_f1", entry_name="My Entry"
        )


class TestResearchCommand:
    def test_requires_query(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["research"])
        assert result.exit_code != 0

    @patch("benchling_agent.interfaces.cli._make_agent")
    def test_research_success(self, mock_make_agent):
        mock_agent = MagicMock()
        mock_make_agent.return_value = mock_agent
        mock_agent.research.return_value = _stub_research_result()

        runner = CliRunner()
        result = runner.invoke(cli, ["research", "--query", "CRISPR design"])

        assert result.exit_code == 0
        assert "CRISPR summary here." in result.output
        mock_agent.research.assert_called_once_with("CRISPR design")


class TestDiscordCommand:
    @patch("benchling_agent.interfaces.cli.get_settings")
    def test_discord_requires_token(self, mock_get_settings):
        from benchling_agent.config import Settings

        mock_get_settings.return_value = Settings(
            _env_file=None,
            anthropic_api_key="",
            benchling_api_url="",
            benchling_api_key="",
            discord_bot_token="",
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["discord"])
        assert result.exit_code == 1
        assert "DISCORD_BOT_TOKEN" in result.output

    @patch("benchling_agent.interfaces.cli.get_settings")
    @patch("benchling_agent.interfaces.discord_bot.run_bot")
    def test_discord_starts_bot(self, mock_run_bot, mock_get_settings):
        from benchling_agent.config import Settings

        mock_get_settings.return_value = Settings(
            _env_file=None,
            anthropic_api_key="k",
            benchling_api_url="https://x.benchling.com",
            benchling_api_key="sk",
            discord_bot_token="tok_test",
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["discord"])
        assert result.exit_code == 0
        assert "Starting Discord bot" in result.output
