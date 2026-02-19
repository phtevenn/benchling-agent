"""Discord bot interface for the Benchling Agent.

Slash commands:
  /configure folder:<str>  — set the default Benchling folder
  /reset                   — clear conversation history
  /finalize                — draft a Benchling entry from the conversation
  /confirm                 — create the pending entry in Benchling
  /cancel                  — discard the pending draft

Free-form messages are handled as multi-turn conversation with Claude.
"""

from __future__ import annotations

import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from benchling_agent.agent import Agent
from benchling_agent.config import Settings
from benchling_agent.session import SessionStore

logger = logging.getLogger(__name__)

MAX_DISCORD_MESSAGE_LENGTH = 2000


def _truncate(text: str, limit: int = MAX_DISCORD_MESSAGE_LENGTH) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _split_message(text: str, limit: int = MAX_DISCORD_MESSAGE_LENGTH) -> list[str]:
    """Split text into chunks that fit within Discord's message length limit.

    Tries to split on newlines to avoid cutting mid-line.
    """
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        # Find the last newline within the limit
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


def create_bot(settings: Settings) -> commands.Bot:
    """Build and return a configured Discord bot (does not start it)."""
    intents = discord.Intents.default()
    intents.message_content = True

    bot = commands.Bot(command_prefix="!", intents=intents)
    agent = Agent(settings=settings)
    session_store = SessionStore()

    @bot.event
    async def on_ready():
        await bot.tree.sync()
        logger.info("Discord bot connected as %s", bot.user)

    # -- Slash commands -------------------------------------------------------

    @bot.tree.command(name="configure", description="Set the default Benchling folder")
    @app_commands.describe(folder="Folder name to search for")
    async def configure(interaction: discord.Interaction, folder: str) -> None:
        try:
            result = await asyncio.to_thread(agent.configure_folder, folder)
            await interaction.response.send_message(
                f"Default folder set to: **{result['name']}** (`{result['id']}`)"
            )
        except ValueError as e:
            await interaction.response.send_message(f"Error: {e}")
        except Exception:
            logger.exception("Error configuring folder")
            await interaction.response.send_message(
                "Something went wrong. Check the logs."
            )

    @bot.tree.command(name="reset", description="Clear conversation history")
    async def reset(interaction: discord.Interaction) -> None:
        session_store.reset(interaction.channel_id)
        await interaction.response.send_message(
            "Conversation cleared. Start a new experiment by chatting."
        )

    @bot.tree.command(
        name="finalize",
        description="Draft a Benchling entry from the conversation",
    )
    async def finalize(interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        session = session_store.get(interaction.channel_id)
        if not session or not session.messages:
            await interaction.followup.send(
                "No conversation yet. Chat first, then finalize."
            )
            return
        try:
            draft = await asyncio.to_thread(agent.propose_entry, session.messages)
            session_store.set_pending_draft(interaction.channel_id, draft)
            preview = f"**Draft entry preview:**\n**Title:** {draft.title}\n\n{draft.body}"
            for chunk in _split_message(preview):
                await interaction.followup.send(chunk)
        except Exception:
            logger.exception("Error finalizing entry")
            await interaction.followup.send(
                "Something went wrong while drafting the entry. Check the logs."
            )

    @bot.tree.command(
        name="confirm",
        description="Create the pending entry in Benchling",
    )
    async def confirm(interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        session = session_store.get(interaction.channel_id)
        if not session or not session.pending_draft:
            await interaction.followup.send(
                "No pending entry. Use /finalize first."
            )
            return
        try:
            result = await asyncio.to_thread(
                agent.create_entry_from_draft, session.pending_draft
            )
            session_store.clear_pending_draft(interaction.channel_id)
            await interaction.followup.send(f"Entry created: {result.web_url}")
        except Exception:
            logger.exception("Error creating entry")
            await interaction.followup.send(
                "Something went wrong while creating the entry. Check the logs."
            )

    @bot.tree.command(name="cancel", description="Discard the pending draft")
    async def cancel(interaction: discord.Interaction) -> None:
        session = session_store.get(interaction.channel_id)
        if not session or not session.pending_draft:
            await interaction.response.send_message("No pending draft to cancel.")
            return
        session_store.clear_pending_draft(interaction.channel_id)
        await interaction.response.send_message(
            "Draft cancelled, resuming conversation."
        )

    # -- Free-form conversation -----------------------------------------------

    @bot.event
    async def on_message(message: discord.Message) -> None:
        if message.author.bot:
            return
        if message.content.startswith("/"):
            return

        session = session_store.get_or_create(message.channel.id)
        try:
            reply, updated_messages = await asyncio.to_thread(
                agent.converse, session.messages, message.content
            )
            session.messages = updated_messages
            await message.channel.send(_truncate(reply))
        except Exception:
            logger.exception("Error in conversation")
            await message.channel.send(
                "Something went wrong. Please try again."
            )

    return bot


def run_bot(settings: Settings) -> None:
    """Create and start the Discord bot (blocking)."""
    bot = create_bot(settings)
    bot.run(settings.discord_bot_token)
