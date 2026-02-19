"""In-memory per-channel conversation session management for the Discord bot."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from benchling_agent.clients.claude import EntryDraft

MAX_MESSAGES = 50


class SessionState(Enum):
    CHATTING = "chatting"
    PENDING_APPROVAL = "pending_approval"


@dataclass
class ConversationSession:
    channel_id: int
    messages: list[dict] = field(default_factory=list)
    pending_draft: EntryDraft | None = None
    state: SessionState = SessionState.CHATTING


class SessionStore:
    """In-memory store keyed by channel_id."""

    def __init__(self) -> None:
        self._sessions: dict[int, ConversationSession] = {}

    def get(self, channel_id: int) -> ConversationSession | None:
        return self._sessions.get(channel_id)

    def get_or_create(self, channel_id: int) -> ConversationSession:
        if channel_id not in self._sessions:
            self._sessions[channel_id] = ConversationSession(channel_id=channel_id)
        return self._sessions[channel_id]

    def add_message(self, channel_id: int, role: str, content: str) -> None:
        session = self.get_or_create(channel_id)
        session.messages.append({"role": role, "content": content})
        if len(session.messages) > MAX_MESSAGES:
            session.messages = session.messages[-MAX_MESSAGES:]

    def set_pending_draft(self, channel_id: int, draft: EntryDraft) -> None:
        session = self.get_or_create(channel_id)
        session.pending_draft = draft
        session.state = SessionState.PENDING_APPROVAL

    def clear_pending_draft(self, channel_id: int) -> None:
        session = self.get_or_create(channel_id)
        session.pending_draft = None
        session.state = SessionState.CHATTING

    def reset(self, channel_id: int) -> None:
        self._sessions.pop(channel_id, None)
