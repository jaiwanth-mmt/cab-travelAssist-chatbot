"""Tests for chat endpoint and memory"""

import pytest
from backend.app.services.memory import SessionMemory, MemoryManager, generate_session_id


def test_generate_session_id():
    """Test session ID generation"""
    session_id = generate_session_id()
    assert isinstance(session_id, str)
    assert len(session_id) > 0


def test_session_memory_creation():
    """Test creating a session memory"""
    session = SessionMemory("test-session-1")
    assert session.session_id == "test-session-1"
    assert len(session.turns) == 0
    assert session.summary is None


def test_add_turn():
    """Test adding conversation turns"""
    session = SessionMemory("test-session-1")
    session.add_turn("user", "Hello")
    session.add_turn("assistant", "Hi, how can I help?")
    
    assert len(session.turns) == 2
    assert session.turns[0].role == "user"
    assert session.turns[0].content == "Hello"


def test_get_recent_turns():
    """Test getting recent turns"""
    session = SessionMemory("test-session-1")
    for i in range(10):
        session.add_turn("user", f"Message {i}")
        session.add_turn("assistant", f"Response {i}")
    
    recent = session.get_recent_turns(n=4)
    assert len(recent) == 4


def test_needs_summarization():
    """Test summarization check"""
    session = SessionMemory("test-session-1")
    assert not session.needs_summarization()
    
    # Add more than max turns
    for i in range(10):
        session.add_turn("user", f"Message {i}")
    
    assert session.needs_summarization()
    
    # After setting summary, should not need it again
    session.set_summary("This is a summary")
    assert not session.needs_summarization()


def test_get_context_for_llm():
    """Test getting formatted context"""
    session = SessionMemory("test-session-1")
    
    # Empty session
    context = session.get_context_for_llm()
    assert "No previous conversation" in context
    
    # With turns
    session.add_turn("user", "What is the search API?")
    session.add_turn("assistant", "The search API is...")
    
    context = session.get_context_for_llm()
    assert "What is the search API?" in context
    assert "The search API is..." in context


def test_memory_manager():
    """Test memory manager"""
    manager = MemoryManager()
    
    # Create new session
    session = manager.get_session("test-session")
    assert session.session_id == "test-session"
    
    # Get existing session
    session2 = manager.get_session("test-session")
    assert session is session2


def test_add_messages():
    """Test adding messages through manager"""
    manager = MemoryManager()
    
    manager.add_user_message("test-session", "Hello")
    manager.add_assistant_message("test-session", "Hi there")
    
    session = manager.get_session("test-session")
    assert len(session.turns) == 2


def test_get_context():
    """Test getting context through manager"""
    manager = MemoryManager()
    
    manager.add_user_message("test-session", "First message")
    manager.add_assistant_message("test-session", "First response")
    
    context = manager.get_context("test-session")
    assert "First message" in context
    assert "First response" in context


def test_session_stats():
    """Test getting session statistics"""
    manager = MemoryManager()
    
    # Non-existent session
    stats = manager.get_session_stats("non-existent")
    assert stats["exists"] is False
    
    # Existing session
    manager.add_user_message("test-session", "Hello")
    stats = manager.get_session_stats("test-session")
    assert stats["exists"] is True
    assert stats["total_turns"] == 1
    assert stats["has_summary"] is False


def test_clear_session():
    """Test clearing a session"""
    manager = MemoryManager()
    
    manager.add_user_message("test-session", "Hello")
    assert "test-session" in manager.get_all_sessions()
    
    result = manager.clear_session("test-session")
    assert result is True
    assert "test-session" not in manager.get_all_sessions()


def test_get_all_sessions():
    """Test getting all session IDs"""
    manager = MemoryManager()
    
    manager.add_user_message("session-1", "Hello")
    manager.add_user_message("session-2", "Hi")
    
    sessions = manager.get_all_sessions()
    assert "session-1" in sessions
    assert "session-2" in sessions


@pytest.mark.skip(reason="Requires running FastAPI server")
def test_chat_endpoint():
    """Test chat endpoint integration"""
    # This would require setting up a test client
    # and having all services available
    pass
