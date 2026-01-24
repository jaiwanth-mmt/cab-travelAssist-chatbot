"""Pinecone vector store integration"""

from typing import List, Dict, Optional
import time
from pinecone import Pinecone, ServerlessSpec

from backend.app.core.config import settings
from backend.app.utils.logger import setup_logger
from backend.app.services.embeddings import get_embedding_service

logger = setup_logger(__name__)


class VectorStore:
    """Pinecone vector store wrapper"""
    
    def __init__(self):
        """Initialize Pinecone client"""
        logger.info("Initializing Pinecone vector store")
        self.pc = Pinecone(api_key=settings.pinecone_api_key)
        self.index_name = settings.pinecone_index_name
        self.embedding_service = get_embedding_service()
        self._index = None
    
    def _get_index(self):
        """Get or create Pinecone index"""
        if self._index is not None:
            return self._index
        
        # Check if index exists
        existing_indexes = [index.name for index in self.pc.list_indexes()]
        
        if self.index_name in existing_indexes:
            # Index exists, check dimension
            index_info = self.pc.describe_index(self.index_name)
            existing_dimension = index_info.dimension
            
            if existing_dimension != settings.embedding_dimension:
                logger.warning(
                    f"Index dimension mismatch: existing={existing_dimension}, "
                    f"required={settings.embedding_dimension}. Deleting and recreating index."
                )
                self.pc.delete_index(self.index_name)
                logger.info(f"Deleted existing index: {self.index_name}")
                # Wait for deletion to complete
                time.sleep(2)
                existing_indexes.remove(self.index_name)
        
        if self.index_name not in existing_indexes:
            logger.info(f"Creating new Pinecone index: {self.index_name}")
            self.pc.create_index(
                name=self.index_name,
                dimension=settings.embedding_dimension,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region="us-east-1"
                )
            )
            # Wait for index to be ready
            logger.info("Waiting for index to be ready...")
            time.sleep(5)
        
        self._index = self.pc.Index(self.index_name)
        logger.info(f"Connected to Pinecone index: {self.index_name}")
        return self._index
    
    def upsert_chunks(
        self,
        chunks: List[Dict],
        batch_size: int = 100
    ) -> Dict:
        """
        Upload chunks to Pinecone with embeddings
        
        Args:
            chunks: List of chunk dictionaries with 'text' and 'metadata'
            batch_size: Number of vectors to upsert at once
            
        Returns:
            Dictionary with upsert statistics
        """
        index = self._get_index()
        
        logger.info(f"Starting upsert of {len(chunks)} chunks")
        start_time = time.time()
        
        # Extract texts for batch embedding
        texts = [chunk['text'] for chunk in chunks]
        
        # Generate embeddings in batch
        logger.info("Generating embeddings for all chunks")
        embeddings = self.embedding_service.embed_batch(texts)
        
        # Prepare vectors for Pinecone
        vectors = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            metadata = chunk['metadata']
            
            # Ensure all fields are never None (Pinecone doesn't accept null values)
            vector = {
                "id": metadata['chunk_id'],
                "values": embedding,
                "metadata": {
                    "text": chunk['text'][:40000],  # Store more text for better context
                    "section_title": metadata.get('section_title', ''),
                    "api_endpoint": metadata.get('api_endpoint', ''),
                    "h1": metadata.get('h1', ''),
                    "h2": metadata.get('h2', ''),
                    "h3": metadata.get('h3', ''),
                    "source": metadata.get('source', ''),
                    "chunk_index": metadata.get('chunk_index', 0),
                    "token_count": metadata.get('token_count', 0)
                }
            }
            vectors.append(vector)
        
        # Upsert in batches
        total_upserted = 0
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            try:
                index.upsert(vectors=batch)
                total_upserted += len(batch)
                logger.info(f"Upserted batch {i // batch_size + 1}: {len(batch)} vectors")
            except Exception as e:
                logger.error(f"Error upserting batch {i // batch_size + 1}: {str(e)}")
                raise
        
        duration = time.time() - start_time
        logger.info(f"Upsert completed: {total_upserted} vectors in {duration:.2f}s")
        
        return {
            "total_upserted": total_upserted,
            "duration_seconds": duration
        }
    
    def semantic_search(
        self,
        query: str,
        top_k: int = None,
        filter_dict: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Search for similar chunks
        
        Args:
            query: Search query text
            top_k: Number of results to return
            filter_dict: Optional metadata filters
            
        Returns:
            List of matches with scores and metadata
        """
        if top_k is None:
            top_k = settings.top_k_results
        
        index = self._get_index()
        
        # Generate query embedding
        query_embedding = self.embedding_service.embed_text(query)
        
        # Search
        try:
            results = index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True,
                filter=filter_dict
            )
        except Exception as e:
            logger.error(f"Error querying Pinecone: {str(e)}")
            raise
        
        # Format results
        matches = []
        for match in results.matches:
            # Apply similarity threshold
            if match.score < settings.similarity_threshold:
                continue
            
            matches.append({
                "id": match.id,
                "score": float(match.score),
                "text": match.metadata.get('text', ''),
                "metadata": {
                    "section_title": match.metadata.get('section_title', ''),
                    "api_endpoint": match.metadata.get('api_endpoint', ''),
                    "h1": match.metadata.get('h1', ''),
                    "h2": match.metadata.get('h2', ''),
                    "h3": match.metadata.get('h3', ''),
                    "source": match.metadata.get('source', ''),
                    "chunk_index": match.metadata.get('chunk_index', 0),
                    "token_count": match.metadata.get('token_count', 0)
                }
            })
        
        logger.info(
            f"Search completed: {len(matches)} matches above threshold "
            f"(total results: {len(results.matches)})"
        )
        
        return matches
    
    def delete_all(self) -> bool:
        """
        Delete all vectors from the index
        
        Returns:
            True if successful
        """
        try:
            index = self._get_index()
            index.delete(delete_all=True)
            logger.info("All vectors deleted from index")
            return True
        except Exception as e:
            logger.error(f"Error deleting vectors: {str(e)}")
            return False
    
    def get_stats(self) -> Dict:
        """
        Get index statistics
        
        Returns:
            Dictionary with index stats
        """
        try:
            index = self._get_index()
            stats = index.describe_index_stats()
            return {
                "total_vectors": stats.total_vector_count,
                "dimension": stats.dimension,
                "index_fullness": stats.index_fullness
            }
        except Exception as e:
            logger.error(f"Error getting index stats: {str(e)}")
            return {}


# Global instance
_vector_store = None


def get_vector_store() -> VectorStore:
    """Get or create the global vector store instance"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
