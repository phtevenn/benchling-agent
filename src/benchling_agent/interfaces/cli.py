"""Click-based CLI interface."""

import click


@click.group()
def cli() -> None:
    """Benchling Agent — AI-powered Benchling entry writer."""


@cli.command()
@click.option("--prompt", "-p", required=True, help="Description of the entry to write.")
def write(prompt: str) -> None:
    """Draft and create a Benchling notebook entry."""
    click.echo(f"[stub] Would write entry from prompt: {prompt}")


@cli.command()
@click.option("--query", "-q", required=True, help="Research question.")
def research(query: str) -> None:
    """Research a topic and summarise findings."""
    click.echo(f"[stub] Would research: {query}")


@cli.command()
def discord() -> None:
    """Start the Discord bot."""
    click.echo("[stub] Would start Discord bot")
