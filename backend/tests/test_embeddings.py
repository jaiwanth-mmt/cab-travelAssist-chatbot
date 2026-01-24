"""Tests for embedding service"""

import pytest
from backend.app.services.embeddings import EmbeddingService, get_embedding_service


def test_embedding_service_singleton():
    """Test that embedding service is a singleton"""
    service1 = get_embedding_service()
    service2 = get_embedding_service()
    assert service1 is service2


def test_embed_text():
    """Test single text embedding"""
    service = get_embedding_service()
    text = "This is a test sentence about cab integration."
    embedding = service.embed_text(text)
    
    assert isinstance(embedding, list)
    assert len(embedding) == 384  # all-MiniLM-L6-v2 dimension
    assert all(isinstance(x, float) for x in embedding)


def test_embed_empty_text():
    """Test embedding empty text"""
    service = get_embedding_service()
    embedding = service.embed_text("")
    
    assert isinstance(embedding, list)
    assert len(embedding) == 384


def test_embed_batch():
    """Test batch embedding"""
    service = get_embedding_service()
    texts = [
        "First test sentence",
        "Second test sentence",
        "Third test sentence"
    ]
    embeddings = service.embed_batch(texts)
    
    assert len(embeddings) == 3
    assert all(len(emb) == 384 for emb in embeddings)


def test_embed_batch_with_empty():
    """Test batch embedding with empty strings"""
    service = get_embedding_service()
    texts = ["Valid text", "", "Another valid text"]
    embeddings = service.embed_batch(texts)
    
    assert len(embeddings) == 3


def test_compute_similarity():
    """Test similarity computation"""
    service = get_embedding_service()
    
    # Same text should have high similarity
    text = "Test sentence"
    emb1 = service.embed_text(text)
    emb2 = service.embed_text(text)
    similarity = service.compute_similarity(emb1, emb2)
    
    assert 0.99 <= similarity <= 1.01  # Account for floating point
    
    # Different texts should have lower similarity
    emb3 = service.embed_text("Completely different content about something else")
    similarity2 = service.compute_similarity(emb1, emb3)
    assert similarity2 < similarity


def test_model_properties():
    """Test model properties"""
    service = get_embedding_service()
    
    assert service.model_name == "sentence-transformers/all-MiniLM-L6-v2"
    assert service.embedding_dim == 384
