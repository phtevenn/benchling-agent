"""Claude (Anthropic) API client wrapper.

Provides a thin, testable layer over the Anthropic SDK with
domain-specific methods for entry writing and research.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import anthropic

from benchling_agent.config import Settings

SYSTEM_PROMPT = (
    "You are a scientific research assistant that helps write Benchling notebook entries. "
    "You produce well-structured, precise, and reproducible experimental documentation. "
    "When asked to write an entry, output structured markdown content. "
    "When asked to research a topic, provide a clear summary with key findings."
)

ENTRY_PROMPT_TEMPLATE = (
    "Write a Benchling notebook entry based on the following description.\n\n"
    "Return your response in EXACTLY this format:\n"
    "TITLE: <a short descriptive title, under 80 characters>\n"
    "BODY:\n"
    "<the body in markdown format>\n\n"
    "Formatting rules for the body:\n"
    "- Use # for Header 1, ## for Header 2, ### for Subheader\n"
    "- Use **bold** for emphasis (e.g. section labels like **Purpose:**)\n"
    "- Use - for bullet lists; indent with 2 spaces per nesting level\n"
    "- Use markdown tables with | column | separators | and a header row\n"
    "- Use blank lines to separate paragraphs and sections\n"
    "- Do NOT use HTML tags\n\n"
    "Description: {prompt}"
)

RESEARCH_PROMPT_TEMPLATE = (
    "Research the following topic and provide a thorough yet concise summary "
    "suitable for inclusion in a lab notebook. Include key findings, relevant "
    "protocols or references where applicable.\n\n"
    "Topic: {query}"
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

    def _send(self, user_message: str, max_tokens: int = 4096) -> ClaudeResponse:
        response = self._client.messages.create(
            model=self.settings.anthropic_model,
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        return ClaudeResponse(
            content=response.content[0].text,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    def draft_entry(self, prompt: str, max_tokens: int = 4096) -> EntryDraft:
        """Generate a title and markdown body for a Benchling notebook entry."""
        user_message = ENTRY_PROMPT_TEMPLATE.format(prompt=prompt)
        response = self._send(user_message, max_tokens=max_tokens)
        title, body = _parse_title_body(response.content)
        return EntryDraft(
            title=title,
            body=body,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

    def research(self, query: str, max_tokens: int = 4096) -> ClaudeResponse:
        """Research a topic and return a summary."""
        user_message = RESEARCH_PROMPT_TEMPLATE.format(query=query)
        return self._send(user_message, max_tokens=max_tokens)


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
