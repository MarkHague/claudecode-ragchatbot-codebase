import pytest
from session_manager import SessionManager


pytestmark = pytest.mark.unit


def test_create_session_returns_unique_ids():
    manager = SessionManager(max_history=5)
    first = manager.create_session()
    second = manager.create_session()
    assert first != second
    assert first == "session_1"
    assert second == "session_2"


def test_add_exchange_stores_user_and_assistant_messages():
    manager = SessionManager(max_history=5)
    session_id = manager.create_session()
    manager.add_exchange(session_id, "What is RAG?", "RAG stands for Retrieval-Augmented Generation.")

    history = manager.get_conversation_history(session_id)
    assert "User: What is RAG?" in history
    assert "Assistant: RAG stands for Retrieval-Augmented Generation." in history


def test_history_trimmed_to_max_history_exchanges():
    manager = SessionManager(max_history=2)
    session_id = manager.create_session()
    for i in range(5):
        manager.add_exchange(session_id, f"question {i}", f"answer {i}")

    # max_history=2 exchanges => at most 4 messages retained
    assert len(manager.sessions[session_id]) == 4
    history = manager.get_conversation_history(session_id)
    assert "question 4" in history
    assert "question 0" not in history


def test_get_conversation_history_returns_none_for_unknown_session():
    manager = SessionManager(max_history=5)
    assert manager.get_conversation_history("nonexistent") is None


def test_get_conversation_history_returns_none_when_session_id_is_none():
    manager = SessionManager(max_history=5)
    assert manager.get_conversation_history(None) is None


def test_clear_session_removes_messages_but_keeps_session():
    manager = SessionManager(max_history=5)
    session_id = manager.create_session()
    manager.add_exchange(session_id, "hi", "hello")
    manager.clear_session(session_id)
    assert manager.get_conversation_history(session_id) is None
    assert session_id in manager.sessions
