"""Claude (Anthropic) API client wrapper.

Provides a thin, testable layer over the Anthropic SDK with
domain-specific methods for conversational experiment planning
and entry drafting.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import anthropic

from benchling_agent.config import Settings

SYSTEM_PROMPT = (
    "You are a conversational experiment planning assistant. "
    "You help scientists plan experiments by discussing objectives, materials, "
    "methods, and expected outcomes through a natural back-and-forth conversation. "
    "Ask clarifying questions when details are missing. "
    "When asked to produce a notebook entry, output structured markdown content."
)

DRAFT_ENTRY_PROMPT = (
    "Based on our conversation so far, draft a Benchling notebook entry. "
    "Return your response in EXACTLY this format:\n"
    "TITLE: <a short descriptive title, under 80 characters>\n"
    "BODY:\n"
    "# Purpose\n<purpose content>\n\n"
    "# Materials\n<materials content>\n\n"
    "# Methods\n<methods content>\n\n"
    "# Results\n\n"
    "Rules:\n"
    "- The body MUST contain exactly these four top-level sections in this order: "
    "Purpose, Materials, Methods, Results.\n"
    "- The Results section MUST be empty (no content below the heading).\n"
    "- Use **bold** for emphasis. Use - for bullet lists.\n"
    "- Use markdown tables with | column | separators | where appropriate.\n"
    "- Do NOT use HTML tags.\n"
)

TITLE_BODY_SEPARATOR = "BODY:"


@dataclass
class ClaudeResponse:
    """Structured response from Claude."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int


@dataclass
class EntryDraft:
    """Title + body from a single Claude call."""

    title: str
    body: str
    model: str
    input_tokens: int
    output_tokens: int


@dataclass
class ClaudeClient:
    """Wrapper around the Anthropic SDK."""

    settings: Settings
    _client: anthropic.Anthropic = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)

    def _send(self, messages: list[dict], max_tokens: int = 4096) -> ClaudeResponse:
        """Send a multi-turn conversation to the Anthropic API.

        Args:
            messages: List of message dicts, each with "role" and "content".
            max_tokens: Maximum tokens in the response.
        """
        response = self._client.messages.create(
            model=self.settings.anthropic_model,
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        return ClaudeResponse(
            content=response.content[0].text,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    def chat(self, messages: list[dict], max_tokens: int = 4096) -> ClaudeResponse:
        """Send a conversational message and get a reply.

        Args:
            messages: Conversation history as a list of {"role": ..., "content": ...} dicts.
            max_tokens: Maximum tokens in the response.
        """
        return self._send(messages, max_tokens=max_tokens)

    def draft_entry_from_conversation(
        self, messages: list[dict], max_tokens: int = 4096
    ) -> EntryDraft:
        """Draft a Benchling entry from conversation history.

        Appends a drafting prompt to the conversation and parses the
        structured TITLE/BODY response. The entry always follows the
        four-section template: Purpose, Materials, Methods, Results
        (Results is always empty).

        Args:
            messages: Conversation history as a list of {"role": ..., "content": ...} dicts.
            max_tokens: Maximum tokens in the response.
        """
        drafting_messages = [
            *messages,
            {"role": "user", "content": DRAFT_ENTRY_PROMPT},
        ]
        response = self._send(drafting_messages, max_tokens=max_tokens)
        title, body = _parse_title_body(response.content)
        return EntryDraft(
            title=title,
            body=body,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

    def draft_entry(self, prompt: str, max_tokens: int = 4096) -> EntryDraft:
        """Generate a title and markdown body for a Benchling notebook entry.

        Convenience wrapper that creates a single-turn conversation from a prompt.
        """
        messages = [{"role": "user", "content": prompt}]
        return self.draft_entry_from_conversation(messages, max_tokens=max_tokens)

    def research(self, query: str, max_tokens: int = 4096) -> ClaudeResponse:
        """Research a topic and return a summary."""
        messages = [
            {
                "role": "user",
                "content": (
                    "Research the following topic and provide a thorough yet concise "
                    "summary suitable for inclusion in a lab notebook. Include key "
                    "findings, relevant protocols or references where applicable.\n\n"
                    f"Topic: {query}"
                ),
            }
        ]
        return self._send(messages, max_tokens=max_tokens)


def _parse_title_body(text: str) -> tuple[str, str]:
    """Parse 'TITLE: ...\nBODY:\n...' format into (title, body)."""
    if TITLE_BODY_SEPARATOR in text:
        before, body = text.split(TITLE_BODY_SEPARATOR, 1)
        title_line = before.strip()
        if title_line.upper().startswith("TITLE:"):
            title_line = title_line[6:]
        title = title_line.strip().strip('"').strip("'")
        return title, body.strip()
    # Fallback: couldn't parse — use first line as title, rest as body
    lines = text.strip().splitlines()
    title = lines[0].strip().strip('"').strip("'")
    if title.upper().startswith("TITLE:"):
        title = title[6:].strip()
    body = "\n".join(lines[1:]).strip()
    return title, body
