"""Discord bot interface for the Benchling Agent.

Commands:
  !configure <folder_name>  — set the default Benchling folder
  !write <prompt>           — draft and create a Benchling entry
  !research <query>         — research a topic via Claude
"""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from benchling_agent.agent import Agent
from benchling_agent.config import Settings

logger = logging.getLogger(__name__)

MAX_DISCORD_MESSAGE_LENGTH = 2000


def _truncate(text: str, limit: int = MAX_DISCORD_MESSAGE_LENGTH) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def create_bot(settings: Settings) -> commands.Bot:
    """Build and return a configured Discord bot (does not start it)."""
    intents = discord.Intents.default()
    intents.message_content = True

    bot = commands.Bot(command_prefix="!", intents=intents)
    agent = Agent(settings=settings)

    @bot.event
    async def on_ready():
        logger.info("Discord bot connected as %s", bot.user)

    @bot.command(name="configure", help="Set default folder: !configure <folder name>")
    async def configure_folder(ctx: commands.Context, *, folder_name: str) -> None:
        try:
            result = agent.configure_folder(folder_name)
            await ctx.send(f"Default folder set to: **{result['name']}** (`{result['id']}`)")
        except ValueError as e:
            await ctx.send(f"Error: {e}")
        except Exception:
            logger.exception("Error configuring folder")
            await ctx.send("Something went wrong. Check the logs.")

    @bot.command(name="write", help="Draft and create a Benchling entry")
    async def write_entry(ctx: commands.Context, *, prompt: str) -> None:
        await ctx.send("Drafting entry with Claude...")
        try:
            result = agent.write_entry(prompt=prompt)
            await ctx.send(f"Entry created: {result.entry.web_url}")
        except ValueError as e:
            await ctx.send(f"Error: {e}")
        except Exception:
            logger.exception("Error writing entry")
            await ctx.send("Something went wrong while writing the entry. Check the logs.")

    @bot.command(name="research", help="Research a topic: !research <query>")
    async def research_topic(ctx: commands.Context, *, query: str) -> None:
        await ctx.send("Researching with Claude...")
        try:
            result = agent.research(query)
            response = (
                f"**Tokens:** {result.response.input_tokens} in / "
                f"{result.response.output_tokens} out\n\n"
                f"{result.response.content}"
            )
            await ctx.send(_truncate(response))
        except Exception:
            logger.exception("Error during research")
            await ctx.send("Something went wrong during research. Check the logs.")

    return bot


def run_bot(settings: Settings) -> None:
    """Create and start the Discord bot (blocking)."""
    bot = create_bot(settings)
    bot.run(settings.discord_bot_token)
