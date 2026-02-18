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
    "When asked to write an entry, output valid HTML suitable for a Benchling notebook entry body. "
    "When asked to research a topic, provide a clear summary with key findings."
)

ENTRY_PROMPT_TEMPLATE = (
    "Write a Benchling notebook entry based on the following description. "
    "Return ONLY the HTML body content (no <html>/<body> wrapper tags). "
    "Use appropriate headings, lists, and tables where helpful.\n\n"
    "Description: {prompt}"
)

RESEARCH_PROMPT_TEMPLATE = (
    "Research the following topic and provide a thorough yet concise summary "
    "suitable for inclusion in a lab notebook. Include key findings, relevant "
    "protocols or references where applicable.\n\n"
    "Topic: {query}"
)


@dataclass
class ClaudeResponse:
    """Structured response from Claude."""

    content: str
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

    def draft_entry(self, prompt: str, max_tokens: int = 4096) -> ClaudeResponse:
        """Generate HTML content for a Benchling notebook entry."""
        user_message = ENTRY_PROMPT_TEMPLATE.format(prompt=prompt)
        return self._send(user_message, max_tokens=max_tokens)

    def research(self, query: str, max_tokens: int = 4096) -> ClaudeResponse:
        """Research a topic and return a summary."""
        user_message = RESEARCH_PROMPT_TEMPLATE.format(query=query)
        return self._send(user_message, max_tokens=max_tokens)
