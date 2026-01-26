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
        logger.info("Initializing Pinecone vector store")
        self.pc = Pinecone(api_key=settings.pinecone_api_key)
        self.index_name = settings.pinecone_index_name
        self.embedding_service = get_embedding_service()
        self._index = None
    
    def _get_index(self):
        if self._index is not None:
            return self._index
        
        existing_indexes = [index.name for index in self.pc.list_indexes()]
        
        if self.index_name in existing_indexes:
            index_info = self.pc.describe_index(self.index_name)
            existing_dimension = index_info.dimension
            
            if existing_dimension != settings.embedding_dimension:
                logger.warning(
                    f"Index dimension mismatch: existing={existing_dimension}, "
                    f"required={settings.embedding_dimension}. Deleting and recreating index."
                )
                self.pc.delete_index(self.index_name)
                logger.info(f"Deleted existing index: {self.index_name}")
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
        """Upload chunks to Pinecone with embeddings"""
        index = self._get_index()
        
        logger.info(f"Starting upsert of {len(chunks)} chunks")
        start_time = time.time()
        
        texts = [chunk['text'] for chunk in chunks]
        
        logger.info("Generating embeddings for all chunks")
        embeddings = self.embedding_service.embed_batch(texts)
        
        vectors = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            metadata = chunk['metadata']
            
            vector = {
                "id": metadata['chunk_id'],
                "values": embedding,
                "metadata": {
                    "text": chunk['text'][:40000],
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
        """Search for similar chunks"""
        if top_k is None:
            top_k = settings.top_k_results
        
        index = self._get_index()
        
        query_embedding = self.embedding_service.embed_text(query)
        
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
        
        matches = []
        for match in results.matches:
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
        try:
            index = self._get_index()
            index.delete(delete_all=True)
            logger.info("All vectors deleted from index")
            return True
        except Exception as e:
            logger.error(f"Error deleting vectors: {str(e)}")
            return False
    
    def get_stats(self) -> Dict:
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


_vector_store = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
