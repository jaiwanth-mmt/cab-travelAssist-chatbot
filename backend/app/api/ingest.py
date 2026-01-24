"""Document ingestion API endpoint"""

import time
from fastapi import APIRouter, HTTPException, status
from typing import Optional

from backend.app.models.requests import IngestRequest
from backend.app.models.responses import IngestResponse, IngestStats, ErrorResponse
from backend.app.services.chunker import chunk_documentation
from backend.app.services.vector_store import get_vector_store
from backend.app.utils.logger import api_logger, log_ingestion_metrics
from backend.app.core.config import settings

router = APIRouter()


@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest documentation into vector store",
    description="Process and ingest the documentation file into the Pinecone vector store. This is a one-time operation that should be run before using the chatbot.",
    responses={
        200: {"description": "Ingestion completed successfully"},
        500: {"description": "Internal server error during ingestion", "model": ErrorResponse}
    }
)
async def ingest_documentation(request: IngestRequest = IngestRequest()):
    """
    Ingest documentation into vector store
    
    This endpoint:
    1. Reads the documentation.txt file
    2. Chunks it into semantic segments
    3. Generates embeddings for each chunk
    4. Uploads to Pinecone vector store
    
    Args:
        request: Optional request body with ingestion options
        
    Returns:
        IngestResponse with statistics
    """
    api_logger.info("Starting documentation ingestion")
    start_time = time.time()
    
    try:
        # Check if we should delete existing vectors
        vector_store = get_vector_store()
        
        if request.force_reindex:
            api_logger.info("Force reindex requested, clearing existing vectors")
            vector_store.delete_all()
            time.sleep(2)  # Wait for deletion to complete
        else:
            # Check if index already has data
            stats = vector_store.get_stats()
            if stats.get('total_vectors', 0) > 0:
                api_logger.warning("Index already contains vectors. Use force_reindex=true to re-ingest")
                return IngestResponse(
                    status="skipped",
                    stats=IngestStats(
                        chunks_created=0,
                        chunks_uploaded=0,
                        time_taken_seconds=0
                    ),
                    message=f"Index already contains {stats['total_vectors']} vectors. Use force_reindex=true to re-ingest."
                )
        
        # Step 1: Chunk the documentation
        api_logger.info(f"Chunking documentation: {settings.documentation_path}")
        chunks = chunk_documentation()
        
        if not chunks:
            raise ValueError("No chunks created from documentation")
        
        api_logger.info(f"Created {len(chunks)} chunks")
        
        # Step 2: Upload to vector store (embeddings are generated inside)
        api_logger.info("Uploading chunks to vector store")
        upsert_result = vector_store.upsert_chunks(chunks)
        
        # Calculate total time
        total_time = time.time() - start_time
        
        # Log metrics
        log_ingestion_metrics(
            api_logger,
            total_chunks=len(chunks),
            duration_seconds=total_time,
            success=True
        )
        
        return IngestResponse(
            status="success",
            stats=IngestStats(
                chunks_created=len(chunks),
                chunks_uploaded=upsert_result['total_upserted'],
                time_taken_seconds=round(total_time, 2)
            ),
            message="Documentation ingested successfully"
        )
        
    except FileNotFoundError as e:
        api_logger.error(f"Documentation file not found: {str(e)}")
        log_ingestion_metrics(
            api_logger,
            total_chunks=0,
            duration_seconds=time.time() - start_time,
            success=False,
            error="File not found"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documentation file not found: {settings.documentation_path}"
        )
    
    except Exception as e:
        api_logger.error(f"Error during ingestion: {str(e)}")
        log_ingestion_metrics(
            api_logger,
            total_chunks=0,
            duration_seconds=time.time() - start_time,
            success=False,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during ingestion: {str(e)}"
        )


@router.get(
    "/ingest/status",
    summary="Check ingestion status",
    description="Get the current status of the vector store"
)
async def get_ingestion_status():
    """Get vector store statistics"""
    try:
        vector_store = get_vector_store()
        stats = vector_store.get_stats()
        return {
            "status": "ok",
            "vector_store": stats
        }
    except Exception as e:
        api_logger.error(f"Error getting ingestion status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting status: {str(e)}"
        )
