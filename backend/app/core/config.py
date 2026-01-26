"""Configuration management using Pydantic Settings"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    azure_openai_key: str
    azure_openai_endpoint: str
    azure_openai_deployment: str
    azure_openai_api_version: str = "2025-01-01-preview"
    
    pinecone_api_key: str
    pinecone_environment: str = "us-east-1"
    pinecone_index_name: str = "mmt-cab-docs"
    
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    
    chunk_size: int = 500
    chunk_overlap: int = 100
    top_k_results: int = 5
    similarity_threshold: float = 0.30
    
    max_conversation_turns: int = 6
    
    llm_temperature: float = 0.05
    llm_max_tokens: int = 1200
    
    log_level: str = "INFO"
    documentation_path: str = "documentation.txt"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


settings = Settings()
