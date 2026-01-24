"""Configuration management using Pydantic Settings"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Azure OpenAI Configuration
    azure_openai_key: str
    azure_openai_endpoint: str
    azure_openai_deployment: str
    azure_openai_api_version: str = "2025-01-01-preview"
    
    # Pinecone Configuration
    pinecone_api_key: str
    pinecone_environment: str = "us-east-1"
    pinecone_index_name: str = "mmt-cab-docs"
    
    # Embedding Configuration
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384  # all-MiniLM-L6-v2 dimension
    
    # RAG Configuration
    chunk_size: int = 500  # Optimal size for semantic chunks
    chunk_overlap: int = 100  # Good overlap for context continuity
    top_k_results: int = 5  # Retrieve more candidates
    similarity_threshold: float = 0.30  # Lower to catch more relevant content
    
    # Memory Configuration
    max_conversation_turns: int = 6  # Keep more history
    
    # LLM Configuration
    llm_temperature: float = 0.05  # Lower temperature for more factual responses
    llm_max_tokens: int = 1200  # Allow longer, more detailed responses
    
    # Logging
    log_level: str = "INFO"
    
    # Documentation
    documentation_path: str = "documentation.txt"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# Global settings instance
settings = Settings()
