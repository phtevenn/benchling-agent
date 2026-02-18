"""Core agent orchestrator — routes user requests to the appropriate action.

The agent currently supports two actions:
  1. write  — use Claude to draft a Benchling notebook entry, then create it
  2. research — use Claude to research a topic and return a summary

The design deliberately keeps action routing simple (explicit enum) so that
new capabilities can be added later without over-engineering an intent-
classification layer up front.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from benchling_agent.clients.benchling import BenchlingClient, EntryResult
from benchling_agent.clients.browser import BenchlingBrowser
from benchling_agent.clients.claude import ClaudeClient, ClaudeResponse, EntryDraft
from benchling_agent.config import Settings, get_settings
from benchling_agent.user_config import UserConfig

logger = logging.getLogger(__name__)


class Action(str, Enum):
    WRITE = "write"
    RESEARCH = "research"


@dataclass
class WriteResult:
    """Result of a write action: the drafted content + the created entry."""

    draft: EntryDraft
    entry: EntryResult
    body_written: bool = False


@dataclass
class ResearchResult:
    """Result of a research action."""

    response: ClaudeResponse


@dataclass
class Agent:
    """Orchestrates Claude and Benchling clients to fulfil user requests."""

    settings: Settings = field(default_factory=get_settings)
    user_config: UserConfig = field(default_factory=UserConfig.load)
    claude: ClaudeClient = field(init=False)
    benchling: BenchlingClient = field(init=False)

    def __post_init__(self) -> None:
        self.claude = ClaudeClient(settings=self.settings)
        self.benchling = BenchlingClient(settings=self.settings)

    def _resolve_folder_id(self, folder_id: str | None) -> str:
        """Return an explicit folder_id, or fall back to the configured default."""
        if folder_id:
            return folder_id
        if self.user_config.default_folder_id:
            return self.user_config.default_folder_id
        raise ValueError(
            "No folder specified and no default configured. "
            "Run 'benchling-agent configure' first."
        )

    def configure_folder(self, folder_name: str) -> dict:
        """Look up a folder by name and save it as the default."""
        folders = self.benchling.list_folders(name_includes=folder_name)
        if not folders:
            raise ValueError(f"No folders found matching '{folder_name}'")
        if len(folders) > 1:
            names = ", ".join(f"'{f['name']}'" for f in folders)
            raise ValueError(
                f"Multiple folders match '{folder_name}': {names}. "
                "Please be more specific."
            )
        folder = folders[0]
        self.user_config.default_folder_id = folder["id"]
        self.user_config.default_folder_name = folder["name"]
        self.user_config.save()
        return folder

    @staticmethod
    def _make_entry_name(title: str) -> str:
        today = date.today().strftime("%Y.%m.%d")
        return f"{today} - {title}"

    def write_entry(
        self,
        prompt: str,
        folder_id: str | None = None,
        entry_name: str | None = None,
    ) -> WriteResult:
        """Draft content with Claude, then create a Benchling entry.

        Claude generates both the title and body in a single API call.
        The entry title is always prefixed with today's date (yyyy.mm.dd).

        Args:
            prompt: Natural-language description of the entry to write.
            folder_id: Benchling folder ID; falls back to configured default.
            entry_name: Optional explicit name; if omitted, Claude generates one.
        """
        resolved_folder = self._resolve_folder_id(folder_id)
        draft = self.claude.draft_entry(prompt)

        title = entry_name or draft.title
        name = self._make_entry_name(title)
        entry = self.benchling.create_entry(name=name, folder_id=resolved_folder)

        body_written = False
        try:
            browser = BenchlingBrowser(settings=self.settings)
            if browser.is_logged_in():
                body_written = browser.write_entry_content(
                    entry.web_url, draft.body
                )
            else:
                logger.warning(
                    "Not logged into Benchling in the browser. "
                    "Run 'benchling-agent login' to authenticate."
                )
            browser.close()
        except Exception:
            logger.warning("Browser automation failed; entry created without body.", exc_info=True)

        return WriteResult(draft=draft, entry=entry, body_written=body_written)

    def research(self, query: str) -> ResearchResult:
        """Research a topic using Claude and return the summary."""
        response = self.claude.research(query)
        return ResearchResult(response=response)
