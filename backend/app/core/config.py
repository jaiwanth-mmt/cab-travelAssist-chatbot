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
    chunk_size: int = 600
    chunk_overlap: int = 75
    top_k_results: int = 4
    similarity_threshold: float = 0.65
    
    # Memory Configuration
    max_conversation_turns: int = 5
    
    # LLM Configuration
    llm_temperature: float = 0.1
    llm_max_tokens: int = 800
    
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
