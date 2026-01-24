"""Hybrid search and re-ranking service"""

import re
from typing import List, Dict, Optional, Set
from collections import Counter

from backend.app.services.vector_store import get_vector_store
from backend.app.core.config import settings
from backend.app.utils.logger import setup_logger

logger = setup_logger(__name__)


class HybridSearchService:
    """
    Combines semantic search with keyword matching and metadata filtering
    """
    
    def __init__(self):
        self.vector_store = get_vector_store()
    
    def _extract_keywords(self, query: str) -> Set[str]:
        """Extract important keywords from query"""
        # Remove common stop words
        stop_words = {
            'the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'but',
            'in', 'with', 'to', 'for', 'of', 'as', 'by', 'from', 'can', 'i',
            'what', 'how', 'do', 'does', 'when', 'where', 'why', 'should'
        }
        
        # Tokenize and clean
        words = re.findall(r'\b\w+\b', query.lower())
        keywords = {w for w in words if w not in stop_words and len(w) > 2}
        
        return keywords
    
    def _keyword_match_score(self, text: str, keywords: Set[str]) -> float:
        """
        Calculate keyword match score for a text
        Returns value between 0 and 1
        """
        if not keywords:
            return 0.0
        
        text_lower = text.lower()
        text_words = set(re.findall(r'\b\w+\b', text_lower))
        
        # Count keyword matches
        matches = keywords.intersection(text_words)
        match_ratio = len(matches) / len(keywords)
        
        # Boost score if keywords appear close together
        proximity_bonus = 0.0
        for keyword in keywords:
            if keyword in text_lower:
                # Count occurrences
                occurrences = text_lower.count(keyword)
                proximity_bonus += min(occurrences * 0.1, 0.3)
        
        total_score = min(match_ratio + proximity_bonus, 1.0)
        return total_score
    
    def _metadata_relevance_score(
        self,
        chunk_metadata: Dict,
        query: str,
        intent: str
    ) -> float:
        """
        Score chunk relevance based on metadata alignment with query
        """
        score = 0.0
        query_lower = query.lower()
        
        # API endpoint match
        api_endpoint = chunk_metadata.get('api_endpoint', '')
        if api_endpoint and api_endpoint.lower() in query_lower:
            score += 0.3
        
        # Section title relevance
        section_title = chunk_metadata.get('section_title', '').lower()
        
        # Check if query mentions section concepts
        if 'booking' in query_lower and 'booking' in section_title:
            score += 0.2
        if 'flow' in query_lower and ('flow' in section_title or 'flowchart' in section_title):
            score += 0.2
        if 'authentication' in query_lower and 'auth' in section_title:
            score += 0.2
        if 'payment' in query_lower and 'payment' in section_title:
            score += 0.2
        if 'tracking' in query_lower and 'tracking' in section_title:
            score += 0.2
        
        # Intent-based boosting
        if intent == "flow" and any(term in section_title for term in ['flow', 'flowchart', 'booking']):
            score += 0.15
        elif intent == "example" and 'example' in section_title:
            score += 0.15
        elif intent == "api_details" and any(term in section_title for term in ['api', 'endpoint']):
            score += 0.15
        
        return min(score, 1.0)
    
    def _calculate_hybrid_score(
        self,
        semantic_score: float,
        keyword_score: float,
        metadata_score: float,
        weights: Dict[str, float] = None
    ) -> float:
        """
        Combine different scores into a hybrid score
        
        Default weights: semantic=0.5, keyword=0.3, metadata=0.2
        """
        if weights is None:
            weights = {
                'semantic': 0.5,
                'keyword': 0.3,
                'metadata': 0.2
            }
        
        hybrid_score = (
            semantic_score * weights['semantic'] +
            keyword_score * weights['keyword'] +
            metadata_score * weights['metadata']
        )
        
        return hybrid_score
    
    def search(
        self,
        query: str,
        intent: str = "general",
        top_k: int = None,
        metadata_filter: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Perform hybrid search combining semantic, keyword, and metadata signals
        
        Args:
            query: Search query
            intent: Query intent (for boosting)
            top_k: Number of results to return
            metadata_filter: Optional metadata filters
            
        Returns:
            List of ranked chunks with scores
        """
        if top_k is None:
            top_k = settings.top_k_results
        
        # Extract keywords for keyword matching
        keywords = self._extract_keywords(query)
        logger.info(f"Extracted keywords: {keywords}")
        
        # Step 1: Semantic search (retrieve more candidates for re-ranking)
        retrieve_k = min(top_k * 3, 20)  # Retrieve 3x more candidates
        semantic_results = self.vector_store.semantic_search(
            query=query,
            top_k=retrieve_k,
            filter_dict=metadata_filter
        )
        
        if not semantic_results:
            logger.warning("No semantic results found")
            return []
        
        logger.info(f"Retrieved {len(semantic_results)} candidates from semantic search")
        
        # Step 2: Re-rank with hybrid scoring
        ranked_results = []
        
        for result in semantic_results:
            semantic_score = result['score']
            text = result['text']
            metadata = result['metadata']
            
            # Calculate keyword match score
            keyword_score = self._keyword_match_score(text, keywords)
            
            # Calculate metadata relevance score
            metadata_score = self._metadata_relevance_score(metadata, query, intent)
            
            # Calculate hybrid score
            hybrid_score = self._calculate_hybrid_score(
                semantic_score,
                keyword_score,
                metadata_score
            )
            
            # Add to results with all scores
            ranked_results.append({
                **result,
                'hybrid_score': hybrid_score,
                'keyword_score': keyword_score,
                'metadata_score': metadata_score,
                'original_semantic_score': semantic_score
            })
        
        # Sort by hybrid score
        ranked_results.sort(key=lambda x: x['hybrid_score'], reverse=True)
        
        # Take top K
        final_results = ranked_results[:top_k]
        
        # Log score distribution
        if final_results:
            avg_hybrid = sum(r['hybrid_score'] for r in final_results) / len(final_results)
            logger.info(
                f"Hybrid search complete: {len(final_results)} results, "
                f"avg_hybrid_score={avg_hybrid:.3f}"
            )
        
        return final_results


class ReRanker:
    """
    Advanced re-ranking using cross-encoder or other techniques
    """
    
    def __init__(self):
        pass
    
    def deduplicate_chunks(self, chunks: List[Dict], similarity_threshold: float = 0.85) -> List[Dict]:
        """
        Remove duplicate or highly similar chunks
        
        Uses text fingerprinting for fast deduplication
        """
        if not chunks:
            return []
        
        seen_fingerprints = set()
        unique_chunks = []
        
        for chunk in chunks:
            text = chunk.get('text', '')
            
            # Create fingerprint (first 300 chars)
            fingerprint = text[:300].strip().lower()
            
            # Calculate simple similarity with existing fingerprints
            is_duplicate = False
            for seen_fp in seen_fingerprints:
                # Simple overlap check
                if len(fingerprint) > 0 and len(seen_fp) > 0:
                    # Count common words
                    fp_words = set(fingerprint.split())
                    seen_words = set(seen_fp.split())
                    
                    if len(fp_words) > 0:
                        overlap = len(fp_words.intersection(seen_words)) / len(fp_words)
                        if overlap > similarity_threshold:
                            is_duplicate = True
                            break
            
            if not is_duplicate:
                seen_fingerprints.add(fingerprint)
                unique_chunks.append(chunk)
        
        logger.info(f"Deduplicated: {len(chunks)} -> {len(unique_chunks)} chunks")
        return unique_chunks
    
    def diversify_results(self, chunks: List[Dict], diversity_threshold: int = 2) -> List[Dict]:
        """
        Ensure diversity by limiting chunks from the same section
        
        Args:
            chunks: List of chunks
            diversity_threshold: Max chunks from same section
        """
        if not chunks:
            return []
        
        section_counts = Counter()
        diversified = []
        
        for chunk in chunks:
            section = chunk['metadata'].get('section_title', 'unknown')
            
            # Add if under threshold
            if section_counts[section] < diversity_threshold:
                diversified.append(chunk)
                section_counts[section] += 1
        
        # If we filtered too much, add back highest scoring chunks
        if len(diversified) < len(chunks) // 2:
            remaining = [c for c in chunks if c not in diversified]
            diversified.extend(remaining[:diversity_threshold])
        
        logger.info(f"Diversified results: {len(chunks)} -> {len(diversified)} chunks")
        return diversified
    
    def rerank(
        self,
        chunks: List[Dict],
        remove_duplicates: bool = True,
        ensure_diversity: bool = True
    ) -> List[Dict]:
        """
        Apply re-ranking post-processing
        
        Args:
            chunks: Initial ranked chunks
            remove_duplicates: Whether to remove duplicates
            ensure_diversity: Whether to ensure section diversity
            
        Returns:
            Re-ranked chunks
        """
        if not chunks:
            return []
        
        result = chunks
        
        # Deduplicate
        if remove_duplicates:
            result = self.deduplicate_chunks(result)
        
        # Diversify
        if ensure_diversity:
            result = self.diversify_results(result)
        
        return result


# Global instances
_hybrid_search_service = None
_reranker = None


def get_hybrid_search_service() -> HybridSearchService:
    """Get or create the global hybrid search service instance"""
    global _hybrid_search_service
    if _hybrid_search_service is None:
        _hybrid_search_service = HybridSearchService()
    return _hybrid_search_service


def get_reranker() -> ReRanker:
    """Get or create the global re-ranker instance"""
    global _reranker
    if _reranker is None:
        _reranker = ReRanker()
    return _reranker
