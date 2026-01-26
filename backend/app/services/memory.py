"""Session memory management with summarization"""

from typing import Dict, List, Optional
from datetime import datetime
import uuid

from backend.app.core.config import settings
from backend.app.core.prompts import SUMMARIZATION_PROMPT
from backend.app.utils.logger import setup_logger

logger = setup_logger(__name__)


class ConversationTurn:
    """Single conversation turn"""
    
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat()
        }


class SessionMemory:
    """Memory for a single conversation session"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.turns: List[ConversationTurn] = []
        self.summary: Optional[str] = None
        self.created_at = datetime.utcnow()
        self.last_accessed = datetime.utcnow()
        self.last_retrieved_chunks: List[Dict] = []
        self.last_query: Optional[str] = None
    
    def add_turn(self, role: str, content: str):
        turn = ConversationTurn(role, content)
        self.turns.append(turn)
        self.last_accessed = datetime.utcnow()
    
    def get_recent_turns(self, n: int = None) -> List[Dict]:
        if n is None:
            n = settings.max_conversation_turns
        return [turn.to_dict() for turn in self.turns[-n:]]
    
    def get_all_turns(self) -> List[Dict]:
        return [turn.to_dict() for turn in self.turns]
    
    def needs_summarization(self) -> bool:
        return len(self.turns) > settings.max_conversation_turns and self.summary is None
    
    def set_summary(self, summary: str):
        self.summary = summary
        logger.info(f"Summary set for session {self.session_id}")
    
    def get_context_for_llm(self) -> str:
        """Get formatted context for LLM"""
        if not self.turns:
            return "No previous conversation."
        
        if len(self.turns) <= settings.max_conversation_turns:
            return self._format_turns(self.turns)
        
        if self.summary:
            recent_turns = self.turns[-4:]
            context = f"Previous conversation summary:\n{self.summary}\n\n"
            context += "Recent conversation:\n"
            context += self._format_turns(recent_turns)
            return context
        else:
            recent_turns = self.turns[-settings.max_conversation_turns:]
            return self._format_turns(recent_turns)
    
    def get_conversation_for_query_rewrite(self) -> List[Dict]:
        recent_turns = self.turns[-5:] if len(self.turns) >= 5 else self.turns
        return [turn.to_dict() for turn in recent_turns]
    
    def _format_turns(self, turns: List[ConversationTurn]) -> str:
        formatted = []
        for turn in turns:
            prefix = "Vendor" if turn.role == "user" else "Assistant"
            formatted.append(f"{prefix}: {turn.content}")
        return "\n".join(formatted)
    
    def get_turns_for_summarization(self) -> str:
        turns_to_summarize = self.turns[:-3] if len(self.turns) > 3 else self.turns
        return self._format_turns(turns_to_summarize)
    
    def cache_retrieved_chunks(self, chunks: List[Dict], query: str):
        self.last_retrieved_chunks = chunks
        self.last_query = query
        logger.info(f"Cached {len(chunks)} chunks for session {self.session_id}")
    
    def get_cached_chunks(self) -> List[Dict]:
        return self.last_retrieved_chunks
    
    def has_cached_chunks(self) -> bool:
        return len(self.last_retrieved_chunks) > 0
    
    def get_last_query(self) -> Optional[str]:
        return self.last_query


class MemoryManager:
    """Manages conversation memory for all sessions"""
    
    def __init__(self):
        self.sessions: Dict[str, SessionMemory] = {}
        logger.info("Memory manager initialized")
    
    def get_session(self, session_id: str) -> SessionMemory:
        if session_id not in self.sessions:
            logger.info(f"Creating new session: {session_id}")
            self.sessions[session_id] = SessionMemory(session_id)
        else:
            self.sessions[session_id].last_accessed = datetime.utcnow()
        
        return self.sessions[session_id]
    
    def add_user_message(self, session_id: str, message: str):
        session = self.get_session(session_id)
        session.add_turn("user", message)
    
    def add_assistant_message(self, session_id: str, message: str):
        session = self.get_session(session_id)
        session.add_turn("assistant", message)
    
    def get_context(self, session_id: str) -> str:
        session = self.get_session(session_id)
        return session.get_context_for_llm()
    
    def get_conversation_for_query_rewrite(self, session_id: str) -> List[Dict]:
        if session_id not in self.sessions:
            return []
        session = self.get_session(session_id)
        return session.get_conversation_for_query_rewrite()
    
    def needs_summarization(self, session_id: str) -> bool:
        if session_id not in self.sessions:
            return False
        return self.sessions[session_id].needs_summarization()
    
    def set_summary(self, session_id: str, summary: str):
        session = self.get_session(session_id)
        session.set_summary(summary)
    
    def get_turns_for_summarization(self, session_id: str) -> str:
        session = self.get_session(session_id)
        return session.get_turns_for_summarization()
    
    def cache_retrieved_chunks(self, session_id: str, chunks: List[Dict], query: str):
        session = self.get_session(session_id)
        session.cache_retrieved_chunks(chunks, query)
    
    def get_cached_chunks(self, session_id: str) -> List[Dict]:
        if session_id not in self.sessions:
            return []
        session = self.get_session(session_id)
        return session.get_cached_chunks()
    
    def has_cached_chunks(self, session_id: str) -> bool:
        if session_id not in self.sessions:
            return False
        session = self.get_session(session_id)
        return session.has_cached_chunks()
    
    def get_last_query(self, session_id: str) -> Optional[str]:
        if session_id not in self.sessions:
            return None
        session = self.get_session(session_id)
        return session.get_last_query()
    
    def get_session_stats(self, session_id: str) -> Dict:
        if session_id not in self.sessions:
            return {"exists": False}
        
        session = self.sessions[session_id]
        return {
            "exists": True,
            "total_turns": len(session.turns),
            "has_summary": session.summary is not None,
            "created_at": session.created_at.isoformat(),
            "last_accessed": session.last_accessed.isoformat()
        }
    
    def clear_session(self, session_id: str) -> bool:
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Session cleared: {session_id}")
            return True
        return False
    
    def get_all_sessions(self) -> List[str]:
        return list(self.sessions.keys())
    
    def cleanup_old_sessions(self, hours: int = 24):
        from datetime import timedelta
        
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=hours)
        
        sessions_to_remove = []
        for session_id, session in self.sessions.items():
            if session.last_accessed < cutoff:
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            del self.sessions[session_id]
            logger.info(f"Cleaned up old session: {session_id}")
        
        return len(sessions_to_remove)


_memory_manager = None


def get_memory_manager() -> MemoryManager:
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager


def generate_session_id() -> str:
    return str(uuid.uuid4())
