"""Tests for in-memory conversation session management."""

from __future__ import annotations

from benchling_agent.clients.claude import EntryDraft
from benchling_agent.session import (
    MAX_MESSAGES,
    ConversationSession,
    SessionState,
    SessionStore,
)


def _stub_draft() -> EntryDraft:
    return EntryDraft(
        title="Test", body="# Body", model="m", input_tokens=1, output_tokens=2
    )


class TestConversationSession:
    def test_defaults(self):
        session = ConversationSession(channel_id=42)
        assert session.channel_id == 42
        assert session.messages == []
        assert session.pending_draft is None
        assert session.state == SessionState.CHATTING


class TestSessionState:
    def test_values(self):
        assert SessionState.CHATTING.value == "chatting"
        assert SessionState.PENDING_APPROVAL.value == "pending_approval"


class TestSessionStore:
    def test_get_returns_none_for_unknown(self):
        store = SessionStore()
        assert store.get(999) is None

    def test_get_or_create_creates_new(self):
        store = SessionStore()
        session = store.get_or_create(1)
        assert isinstance(session, ConversationSession)
        assert session.channel_id == 1

    def test_get_or_create_returns_existing(self):
        store = SessionStore()
        s1 = store.get_or_create(1)
        s2 = store.get_or_create(1)
        assert s1 is s2

    def test_add_message(self):
        store = SessionStore()
        store.add_message(1, "user", "hello")
        session = store.get(1)
        assert session is not None
        assert len(session.messages) == 1
        assert session.messages[0] == {"role": "user", "content": "hello"}

    def test_add_message_rolling_window(self):
        store = SessionStore()
        for i in range(MAX_MESSAGES + 10):
            store.add_message(1, "user", f"msg {i}")
        session = store.get(1)
        assert len(session.messages) == MAX_MESSAGES
        # Oldest messages should be trimmed; newest should remain
        assert session.messages[0]["content"] == "msg 10"
        assert session.messages[-1]["content"] == f"msg {MAX_MESSAGES + 9}"

    def test_set_pending_draft(self):
        store = SessionStore()
        draft = _stub_draft()
        store.set_pending_draft(1, draft)
        session = store.get(1)
        assert session.pending_draft is draft
        assert session.state == SessionState.PENDING_APPROVAL

    def test_clear_pending_draft(self):
        store = SessionStore()
        store.set_pending_draft(1, _stub_draft())
        store.clear_pending_draft(1)
        session = store.get(1)
        assert session.pending_draft is None
        assert session.state == SessionState.CHATTING

    def test_reset(self):
        store = SessionStore()
        store.add_message(1, "user", "hello")
        store.reset(1)
        assert store.get(1) is None

    def test_reset_nonexistent_is_noop(self):
        store = SessionStore()
        store.reset(999)  # should not raise

    def test_state_transitions(self):
        store = SessionStore()
        session = store.get_or_create(1)
        assert session.state == SessionState.CHATTING

        store.set_pending_draft(1, _stub_draft())
        assert session.state == SessionState.PENDING_APPROVAL

        store.clear_pending_draft(1)
        assert session.state == SessionState.CHATTING
