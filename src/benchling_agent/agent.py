"""Core agent orchestrator — routes user requests to the appropriate action.

The agent currently supports two actions:
  1. write  — use Claude to draft a Benchling notebook entry, then create it
  2. research — use Claude to research a topic and return a summary

The design deliberately keeps action routing simple (explicit enum) so that
new capabilities can be added later without over-engineering an intent-
classification layer up front.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from benchling_agent.clients.benchling import BenchlingClient, EntryResult
from benchling_agent.clients.claude import ClaudeClient, ClaudeResponse
from benchling_agent.config import Settings, get_settings


class Action(str, Enum):
    WRITE = "write"
    RESEARCH = "research"


@dataclass
class WriteResult:
    """Result of a write action: the drafted content + the created entry."""

    draft: ClaudeResponse
    entry: EntryResult


@dataclass
class ResearchResult:
    """Result of a research action."""

    response: ClaudeResponse


@dataclass
class Agent:
    """Orchestrates Claude and Benchling clients to fulfil user requests."""

    settings: Settings = field(default_factory=get_settings)
    claude: ClaudeClient = field(init=False)
    benchling: BenchlingClient = field(init=False)

    def __post_init__(self) -> None:
        self.claude = ClaudeClient(settings=self.settings)
        self.benchling = BenchlingClient(settings=self.settings)

    def write_entry(
        self,
        prompt: str,
        folder_id: str,
        entry_name: str | None = None,
    ) -> WriteResult:
        """Draft content with Claude, then create a Benchling entry.

        Args:
            prompt: Natural-language description of the entry to write.
            folder_id: Benchling folder ID to create the entry in.
            entry_name: Optional explicit name; defaults to first 60 chars of prompt.
        """
        draft = self.claude.draft_entry(prompt)

        name = entry_name or prompt[:60].strip()
        entry = self.benchling.create_entry(name=name, folder_id=folder_id)

        return WriteResult(draft=draft, entry=entry)

    def research(self, query: str) -> ResearchResult:
        """Research a topic using Claude and return the summary."""
        response = self.claude.research(query)
        return ResearchResult(response=response)
