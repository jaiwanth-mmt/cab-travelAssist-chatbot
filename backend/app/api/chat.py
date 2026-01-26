"""Chat API endpoint with enhanced RAG"""

import time
from fastapi import APIRouter, HTTPException, status
from typing import List, Dict

from backend.app.models.requests import ChatRequest
from backend.app.models.responses import (
    ChatResponse,
    ChatMetadata,
    ConfidenceLevel,
    ErrorResponse
)
from backend.app.services.query_processor import get_query_preprocessor
from backend.app.services.hybrid_search import get_hybrid_search_service, get_reranker
from backend.app.services.memory import get_memory_manager
from backend.app.services.llm import get_llm_service
from backend.app.utils.logger import api_logger, log_query_metrics
from backend.app.core.config import settings
from backend.app.core.prompts import NO_RELEVANT_CONTEXT_MESSAGE, CONVERSATIONAL_RESPONSES

router = APIRouter()


def determine_confidence(avg_similarity: float, num_chunks: int) -> ConfidenceLevel:
    if num_chunks == 0 or avg_similarity < settings.similarity_threshold:
        return ConfidenceLevel.NONE
    elif avg_similarity >= 0.78:
        return ConfidenceLevel.HIGH
    elif avg_similarity >= 0.68:
        return ConfidenceLevel.MEDIUM
    else:
        return ConfidenceLevel.LOW


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Chat with the travel assist bot",
    description="Send a query to the chatbot and receive an answer based on the documentation.",
    responses={
        200: {"description": "Successful response with answer"},
        400: {"description": "Invalid request", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def chat(request: ChatRequest) -> ChatResponse:
    """Process a chat query with enhanced RAG pipeline"""
    api_logger.info(f"Chat request: session={request.session_id}, query={request.user_query[:100]}")
    start_time = time.time()
    
    try:
        query_preprocessor = get_query_preprocessor()
        hybrid_search = get_hybrid_search_service()
        reranker = get_reranker()
        memory_manager = get_memory_manager()
        llm_service = get_llm_service()
        
        memory_manager.add_user_message(request.session_id, request.user_query)
        conversation_history = memory_manager.get_conversation_for_query_rewrite(request.session_id)
        
        api_logger.info("Preprocessing query")
        query_info = query_preprocessor.preprocess(
            query=request.user_query,
            conversation_history=conversation_history
        )
        
        processed_query = query_info["processed_query"]
        intent = query_info["intent"]
        is_meta_query = query_info.get("is_meta_query", False)
        is_conversational = query_info.get("is_conversational", False)
        conversation_type = query_info.get("conversation_type")
        
        if is_conversational:
            api_logger.info(f"Conversational query detected: {conversation_type}")
            response_text = CONVERSATIONAL_RESPONSES.get(
                conversation_type,
                "Hello! I'm here to help you with MakeMyTrip cab vendor integration. How can I assist you today?"
            )
            memory_manager.add_assistant_message(request.session_id, response_text)
            latency = (time.time() - start_time) * 1000
            
            return ChatResponse(
                session_id=request.session_id,
                answer=response_text,
                sources=[],
                confidence=ConfidenceLevel.HIGH,
                metadata=ChatMetadata(
                    retrieved_chunks=0,
                    avg_similarity=1.0,
                    latency_ms=round(latency, 2)
                )
            )
        
        api_logger.info(f"Query intent: {intent}, is_meta: {is_meta_query}, processed: {processed_query[:100]}")
        
        retrieved_chunks = []
        used_cache = False
        
        if is_meta_query and memory_manager.has_cached_chunks(request.session_id):
            api_logger.info("Meta-query detected - reusing cached chunks from previous turn")
            retrieved_chunks = memory_manager.get_cached_chunks(request.session_id)
            used_cache = True
        else:
            api_logger.info("Performing hybrid search")
            retrieved_chunks = hybrid_search.search(
                query=processed_query,
                intent=intent,
                top_k=settings.top_k_results
            )
            
            if retrieved_chunks:
                api_logger.info("Applying re-ranking")
                retrieved_chunks = reranker.rerank(
                    chunks=retrieved_chunks,
                    remove_duplicates=True,
                    ensure_diversity=True
                )
        
        if not retrieved_chunks:
            api_logger.warning("No relevant chunks found after hybrid search and re-ranking")
            memory_manager.add_assistant_message(request.session_id, NO_RELEVANT_CONTEXT_MESSAGE)
            latency = (time.time() - start_time) * 1000
            
            log_query_metrics(
                api_logger,
                session_id=request.session_id,
                query=request.user_query,
                retrieved_chunks=0,
                avg_similarity=0.0,
                latency_ms=latency,
                confidence="none"
            )
            
            return ChatResponse(
                session_id=request.session_id,
                answer=NO_RELEVANT_CONTEXT_MESSAGE,
                sources=[],
                confidence=ConfidenceLevel.NONE,
                metadata=ChatMetadata(
                    retrieved_chunks=0,
                    avg_similarity=0.0,
                    latency_ms=round(latency, 2)
                )
            )
        
        avg_similarity = sum(chunk.get('hybrid_score', chunk.get('score', 0)) for chunk in retrieved_chunks) / len(retrieved_chunks)
        api_logger.info(f"Retrieved {len(retrieved_chunks)} chunks, avg hybrid score: {avg_similarity:.3f}")
        
        memory_context = memory_manager.get_context(request.session_id)
        
        if memory_manager.needs_summarization(request.session_id):
            api_logger.info("Conversation needs summarization")
            turns_to_summarize = memory_manager.get_turns_for_summarization(request.session_id)
            summary = await llm_service.summarize_conversation(turns_to_summarize)
            memory_manager.set_summary(request.session_id, summary)
            memory_context = memory_manager.get_context(request.session_id)
        
        api_logger.info("Generating answer with LLM")
        answer, sources = await llm_service.generate_answer(
            query=request.user_query,
            context=retrieved_chunks,
            memory=memory_context
        )
        
        memory_manager.add_assistant_message(request.session_id, answer)
        
        if not used_cache:
            memory_manager.cache_retrieved_chunks(request.session_id, retrieved_chunks, request.user_query)
        
        confidence = determine_confidence(avg_similarity, len(retrieved_chunks))
        latency = (time.time() - start_time) * 1000
        
        log_query_metrics(
            api_logger,
            session_id=request.session_id,
            query=request.user_query,
            retrieved_chunks=len(retrieved_chunks),
            avg_similarity=avg_similarity,
            latency_ms=latency,
            confidence=confidence.value
        )
        
        return ChatResponse(
            session_id=request.session_id,
            answer=answer,
            sources=sources,
            confidence=confidence,
            metadata=ChatMetadata(
                retrieved_chunks=len(retrieved_chunks),
                avg_similarity=round(avg_similarity, 3),
                latency_ms=round(latency, 2)
            )
        )
        
    except ValueError as e:
        api_logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    except Exception as e:
        api_logger.error(f"Error processing chat request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing request: {str(e)}"
        )


@router.get(
    "/session/{session_id}",
    summary="Get session information",
    description="Retrieve information about a conversation session"
)
async def get_session_info(session_id: str):
    try:
        memory_manager = get_memory_manager()
        stats = memory_manager.get_session_stats(session_id)
        return {
            "session_id": session_id,
            **stats
        }
    except Exception as e:
        api_logger.error(f"Error getting session info: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting session info: {str(e)}"
        )


@router.delete(
    "/session/{session_id}",
    summary="Clear session",
    description="Clear conversation history for a session"
)
async def clear_session(session_id: str):
    try:
        memory_manager = get_memory_manager()
        success = memory_manager.clear_session(session_id)
        if success:
            return {"status": "success", "message": f"Session {session_id} cleared"}
        else:
            return {"status": "not_found", "message": f"Session {session_id} not found"}
    except Exception as e:
        api_logger.error(f"Error clearing session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error clearing session: {str(e)}"
        )
