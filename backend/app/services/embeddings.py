"""Embedding service using Sentence Transformers"""

from typing import List, Union
from sentence_transformers import SentenceTransformer
import numpy as np

from backend.app.core.config import settings
from backend.app.utils.logger import setup_logger

logger = setup_logger(__name__)


class EmbeddingService:
    """Wrapper for Sentence Transformers embedding model"""
    
    _instance = None
    _model = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._model is None:
            logger.info(f"Loading embedding model: {settings.embedding_model}")
            self._model = SentenceTransformer(settings.embedding_model)
            logger.info("Embedding model loaded successfully")
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return [0.0] * settings.embedding_dimension
        
        try:
            embedding = self._model.encode(
                text,
                normalize_embeddings=True,
                show_progress_bar=False
            )
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise
    
    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        if not texts:
            logger.warning("Empty text list provided for batch embedding")
            return []
        
        valid_texts = []
        valid_indices = []
        for i, text in enumerate(texts):
            if text and text.strip():
                valid_texts.append(text)
                valid_indices.append(i)
        
        if not valid_texts:
            logger.warning("No valid texts in batch")
            return [[0.0] * settings.embedding_dimension] * len(texts)
        
        try:
            logger.info(f"Generating embeddings for {len(valid_texts)} texts")
            
            embeddings = self._model.encode(
                valid_texts,
                normalize_embeddings=True,
                batch_size=batch_size,
                show_progress_bar=len(valid_texts) > 50
            )
            
            result = [[0.0] * settings.embedding_dimension] * len(texts)
            
            for idx, embedding in zip(valid_indices, embeddings):
                result[idx] = embedding.tolist()
            
            logger.info(f"Successfully generated {len(valid_texts)} embeddings")
            return result
            
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {str(e)}")
            raise
    
    def compute_similarity(
        self,
        embedding1: Union[List[float], np.ndarray],
        embedding2: Union[List[float], np.ndarray]
    ) -> float:
        """Compute cosine similarity between two embeddings"""
        if isinstance(embedding1, list):
            embedding1 = np.array(embedding1)
        if isinstance(embedding2, list):
            embedding2 = np.array(embedding2)
        
        similarity = np.dot(embedding1, embedding2) / (
            np.linalg.norm(embedding1) * np.linalg.norm(embedding2)
        )
        
        return float(similarity)
    
    @property
    def model_name(self) -> str:
        return settings.embedding_model
    
    @property
    def embedding_dim(self) -> int:
        return settings.embedding_dimension


_embedding_service = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
