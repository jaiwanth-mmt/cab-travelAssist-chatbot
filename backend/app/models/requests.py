"""Pydantic request models"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional


class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    
    session_id: str = Field(
        ...,
        description="Unique session identifier for conversation tracking",
        min_length=1,
        max_length=100
    )
    user_query: str = Field(
        ...,
        description="User's question or query",
        min_length=1,
        max_length=2000
    )
    
    @field_validator('session_id')
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        """Validate session ID format"""
        if not v or not v.strip():
            raise ValueError("Session ID cannot be empty")
        return v.strip()
    
    @field_validator('user_query')
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate and clean query"""
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "session_id": "vendor-session-123",
                    "user_query": "How do I call the search API?"
                }
            ]
        }
    }


class IngestRequest(BaseModel):
    """Request model for ingestion endpoint"""
    
    force_reindex: bool = Field(
        default=False,
        description="Force re-indexing even if index already exists"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "force_reindex": False
                }
            ]
        }
    }
