"""Click-based CLI interface for the Benchling Agent."""

from __future__ import annotations

import click

from benchling_agent.agent import Agent
from benchling_agent.config import get_settings


def _make_agent() -> Agent:
    return Agent(settings=get_settings())


@click.group()
@click.version_option(package_name="benchling-agent")
def cli() -> None:
    """Benchling Agent — AI-powered Benchling entry writer."""


@cli.command()
@click.option("--prompt", "-p", required=True, help="Description of the entry to write.")
@click.option("--folder-id", "-f", default=None, help="Benchling folder ID (optional).")
@click.option("--name", "-n", default=None, help="Entry name (defaults to truncated prompt).")
def write(prompt: str, folder_id: str | None, name: str | None) -> None:
    """Draft and create a Benchling notebook entry."""
    agent = _make_agent()
    click.echo("Drafting entry with Claude...")
    try:
        result = agent.write_entry(prompt=prompt, folder_id=folder_id, entry_name=name)
    except ValueError as e:
        click.echo(f"Error: {e}")
        raise SystemExit(1)

    click.echo(f"\nEntry created: {result.entry.name}")
    click.echo(f"  URL: {result.entry.web_url}")
    click.echo("\n--- Draft body (paste into entry) ---")
    click.echo(result.draft.content)


@cli.command()
@click.option("--folder", "-f", required=True, help="Folder name to search for and set as default.")
def configure(folder: str) -> None:
    """Set the default Benchling folder by name."""
    agent = _make_agent()
    try:
        result = agent.configure_folder(folder)
    except ValueError as e:
        click.echo(f"Error: {e}")
        raise SystemExit(1)
    click.echo(f"Default folder set to: {result['name']} ({result['id']})")


@cli.command()
@click.option("--query", "-q", required=True, help="Research question.")
def research(query: str) -> None:
    """Research a topic and summarise findings."""
    agent = _make_agent()
    click.echo("Researching with Claude...")
    result = agent.research(query)

    inp, out = result.response.input_tokens, result.response.output_tokens
    click.echo(f"\nTokens used: {inp} in / {out} out")
    click.echo("\n--- Research summary ---")
    click.echo(result.response.content)


@cli.command()
def discord() -> None:
    """Start the Discord bot."""
    from benchling_agent.interfaces.discord_bot import run_bot

    settings = get_settings()
    if not settings.discord_bot_token:
        click.echo("Error: DISCORD_BOT_TOKEN is not set. See .env.example.")
        raise SystemExit(1)
    click.echo("Starting Discord bot...")
    run_bot(settings)
