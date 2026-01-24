"""Pydantic response models"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class ConfidenceLevel(str, Enum):
    """Confidence levels for answers"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class ChatMetadata(BaseModel):
    """Metadata about the chat response"""
    
    retrieved_chunks: int = Field(
        ...,
        description="Number of chunks retrieved from vector store"
    )
    avg_similarity: float = Field(
        ...,
        description="Average similarity score of retrieved chunks"
    )
    latency_ms: float = Field(
        ...,
        description="Total processing time in milliseconds"
    )


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    
    session_id: str = Field(
        ...,
        description="Session identifier"
    )
    answer: str = Field(
        ...,
        description="Generated answer to the user's query"
    )
    sources: List[str] = Field(
        default_factory=list,
        description="List of documentation sections used to generate the answer"
    )
    confidence: ConfidenceLevel = Field(
        ...,
        description="Confidence level of the answer"
    )
    metadata: ChatMetadata = Field(
        ...,
        description="Additional metadata about the response"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "session_id": "vendor-session-123",
                    "answer": "The Search API is called by sending a POST request to your partner search endpoint...",
                    "sources": ["Normal Booking Flow - Search", "API Flowchart"],
                    "confidence": "high",
                    "metadata": {
                        "retrieved_chunks": 4,
                        "avg_similarity": 0.82,
                        "latency_ms": 450.5
                    }
                }
            ]
        }
    }


class IngestStats(BaseModel):
    """Statistics from document ingestion"""
    
    chunks_created: int = Field(
        ...,
        description="Number of chunks created from the document"
    )
    chunks_uploaded: int = Field(
        ...,
        description="Number of chunks successfully uploaded to vector store"
    )
    time_taken_seconds: float = Field(
        ...,
        description="Total time taken for ingestion in seconds"
    )


class IngestResponse(BaseModel):
    """Response model for ingest endpoint"""
    
    status: str = Field(
        ...,
        description="Status of the ingestion process"
    )
    stats: IngestStats = Field(
        ...,
        description="Ingestion statistics"
    )
    message: Optional[str] = Field(
        None,
        description="Additional message or notes"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "success",
                    "stats": {
                        "chunks_created": 250,
                        "chunks_uploaded": 250,
                        "time_taken_seconds": 45.2
                    },
                    "message": "Documentation ingested successfully"
                }
            ]
        }
    }


class HealthResponse(BaseModel):
    """Response model for health check"""
    
    status: str = Field(
        ...,
        description="Overall health status"
    )
    version: str = Field(
        ...,
        description="Application version"
    )
    services: Dict[str, str] = Field(
        default_factory=dict,
        description="Status of individual services"
    )


class ErrorResponse(BaseModel):
    """Generic error response"""
    
    error: str = Field(
        ...,
        description="Error type or category"
    )
    message: str = Field(
        ...,
        description="Detailed error message"
    )
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional error details"
    )
