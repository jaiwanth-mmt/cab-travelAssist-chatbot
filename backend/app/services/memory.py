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
        self.role = role  # 'user' or 'assistant'
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
    
    def add_turn(self, role: str, content: str):
        """Add a conversation turn"""
        turn = ConversationTurn(role, content)
        self.turns.append(turn)
        self.last_accessed = datetime.utcnow()
    
    def get_recent_turns(self, n: int = None) -> List[Dict]:
        """Get the N most recent turns"""
        if n is None:
            n = settings.max_conversation_turns
        return [turn.to_dict() for turn in self.turns[-n:]]
    
    def get_all_turns(self) -> List[Dict]:
        """Get all conversation turns"""
        return [turn.to_dict() for turn in self.turns]
    
    def needs_summarization(self) -> bool:
        """Check if conversation needs summarization"""
        return len(self.turns) > settings.max_conversation_turns and self.summary is None
    
    def set_summary(self, summary: str):
        """Set conversation summary"""
        self.summary = summary
        logger.info(f"Summary set for session {self.session_id}")
    
    def get_context_for_llm(self) -> str:
        """
        Get formatted context for LLM with better structure
        
        Returns conversation history as a formatted string.
        If conversation is long, returns summary + recent turns.
        """
        if not self.turns:
            return "No previous conversation."
        
        # Short conversation: return all turns
        if len(self.turns) <= settings.max_conversation_turns:
            return self._format_turns(self.turns)
        
        # Long conversation: return summary + recent turns
        if self.summary:
            recent_turns = self.turns[-4:]  # Last 4 turns for more context
            context = f"Previous conversation summary:\n{self.summary}\n\n"
            context += "Recent conversation:\n"
            context += self._format_turns(recent_turns)
            return context
        else:
            # No summary yet, return recent turns only
            recent_turns = self.turns[-settings.max_conversation_turns:]
            return self._format_turns(recent_turns)
    
    def get_conversation_for_query_rewrite(self) -> List[Dict]:
        """
        Get conversation history for query rewriting
        Returns last N turns as list of dicts
        """
        recent_turns = self.turns[-5:] if len(self.turns) >= 5 else self.turns
        return [turn.to_dict() for turn in recent_turns]
    
    def _format_turns(self, turns: List[ConversationTurn]) -> str:
        """Format turns as readable text"""
        formatted = []
        for turn in turns:
            prefix = "Vendor" if turn.role == "user" else "Assistant"
            formatted.append(f"{prefix}: {turn.content}")
        return "\n".join(formatted)
    
    def get_turns_for_summarization(self) -> str:
        """Get turns to summarize (exclude the most recent ones)"""
        # Summarize all but the last 3 turns
        turns_to_summarize = self.turns[:-3] if len(self.turns) > 3 else self.turns
        return self._format_turns(turns_to_summarize)


class MemoryManager:
    """Manages conversation memory for all sessions"""
    
    def __init__(self):
        self.sessions: Dict[str, SessionMemory] = {}
        logger.info("Memory manager initialized")
    
    def get_session(self, session_id: str) -> SessionMemory:
        """
        Get or create a session
        
        Args:
            session_id: Session identifier
            
        Returns:
            SessionMemory instance
        """
        if session_id not in self.sessions:
            logger.info(f"Creating new session: {session_id}")
            self.sessions[session_id] = SessionMemory(session_id)
        else:
            self.sessions[session_id].last_accessed = datetime.utcnow()
        
        return self.sessions[session_id]
    
    def add_user_message(self, session_id: str, message: str):
        """Add user message to session"""
        session = self.get_session(session_id)
        session.add_turn("user", message)
    
    def add_assistant_message(self, session_id: str, message: str):
        """Add assistant message to session"""
        session = self.get_session(session_id)
        session.add_turn("assistant", message)
    
    def get_context(self, session_id: str) -> str:
        """Get formatted conversation context for LLM"""
        session = self.get_session(session_id)
        return session.get_context_for_llm()
    
    def get_conversation_for_query_rewrite(self, session_id: str) -> List[Dict]:
        """Get conversation history for query rewriting"""
        if session_id not in self.sessions:
            return []
        session = self.get_session(session_id)
        return session.get_conversation_for_query_rewrite()
    
    def needs_summarization(self, session_id: str) -> bool:
        """Check if session needs summarization"""
        if session_id not in self.sessions:
            return False
        return self.sessions[session_id].needs_summarization()
    
    def set_summary(self, session_id: str, summary: str):
        """Set summary for session"""
        session = self.get_session(session_id)
        session.set_summary(summary)
    
    def get_turns_for_summarization(self, session_id: str) -> str:
        """Get conversation turns that need summarization"""
        session = self.get_session(session_id)
        return session.get_turns_for_summarization()
    
    def get_session_stats(self, session_id: str) -> Dict:
        """Get statistics about a session"""
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
        """Clear a session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Session cleared: {session_id}")
            return True
        return False
    
    def get_all_sessions(self) -> List[str]:
        """Get list of all session IDs"""
        return list(self.sessions.keys())
    
    def cleanup_old_sessions(self, hours: int = 24):
        """Remove sessions older than specified hours"""
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


# Global memory manager instance
_memory_manager = None


def get_memory_manager() -> MemoryManager:
    """Get or create the global memory manager instance"""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager


def generate_session_id() -> str:
    """Generate a new session ID"""
    return str(uuid.uuid4())
