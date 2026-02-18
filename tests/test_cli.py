"""Tests for the CLI interface."""

from click.testing import CliRunner

from benchling_agent.interfaces.cli import cli


class TestCli:
    def test_write_command_requires_prompt(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["write"])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "required" in result.output.lower()

    def test_write_command_stub(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["write", "--prompt", "test prompt"])
        assert result.exit_code == 0
        assert "test prompt" in result.output

    def test_research_command_stub(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["research", "--query", "test query"])
        assert result.exit_code == 0
        assert "test query" in result.output

    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Benchling Agent" in result.output
