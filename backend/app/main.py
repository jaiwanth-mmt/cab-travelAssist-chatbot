"""FastAPI application entry point"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import time
from contextlib import asynccontextmanager

from backend.app.api import chat, ingest
from backend.app.models.responses import HealthResponse, ErrorResponse
from backend.app.utils.logger import app_logger, api_logger
from backend.app.services.embeddings import get_embedding_service
from backend.app.core.config import settings
from backend.app import __version__


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_logger.info("Starting Travel Assist Chatbot API")
    app_logger.info(f"Version: {__version__}")
    
    try:
        app_logger.info("Pre-loading embedding model...")
        embedding_service = get_embedding_service()
        app_logger.info(f"Embedding model loaded: {embedding_service.model_name}")
    except Exception as e:
        app_logger.error(f"Error loading embedding model: {str(e)}")
    
    yield
    
    app_logger.info("Shutting down Travel Assist Chatbot API")


app = FastAPI(
    title="MakeMyTrip Cab Vendor Travel Assist Chatbot",
    description="A RAG-based chatbot to help cab vendors integrate with the MakeMyTrip platform",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    api_logger.info(
        f"Request: {request.method} {request.url.path}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "client": request.client.host if request.client else None
        }
    )
    
    response = await call_next(request)
    
    duration = (time.time() - start_time) * 1000
    api_logger.info(
        f"Response: {response.status_code} ({duration:.2f}ms)",
        extra={
            "status_code": response.status_code,
            "duration_ms": round(duration, 2)
        }
    )
    
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    api_logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "message": "Invalid request data",
            "details": exc.errors()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    api_logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "details": str(exc) if settings.log_level == "DEBUG" else None
        }
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check if the API is running and services are healthy",
    tags=["Health"]
)
async def health_check():
    services = {}
    
    try:
        embedding_service = get_embedding_service()
        services["embeddings"] = "ok"
    except Exception as e:
        services["embeddings"] = f"error: {str(e)}"
    
    try:
        from backend.app.services.vector_store import get_vector_store
        vector_store = get_vector_store()
        stats = vector_store.get_stats()
        services["vector_store"] = f"ok (vectors: {stats.get('total_vectors', 0)})"
    except Exception as e:
        services["vector_store"] = f"error: {str(e)}"
    
    try:
        from backend.app.services.llm import get_llm_service
        llm_service = get_llm_service()
        services["llm"] = "ok"
    except Exception as e:
        services["llm"] = f"error: {str(e)}"
    
    overall_status = "healthy" if all("ok" in v for v in services.values()) else "degraded"
    
    return HealthResponse(
        status=overall_status,
        version=__version__,
        services=services
    )


@app.get(
    "/",
    summary="API Information",
    description="Get basic information about the API",
    tags=["Info"]
)
async def root():
    return {
        "name": "MakeMyTrip Cab Vendor Travel Assist Chatbot",
        "version": __version__,
        "description": "A RAG-based chatbot to help cab vendors integrate with the MakeMyTrip platform",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "chat": "/chat",
            "ingest": "/ingest"
        }
    }


app.include_router(chat.router, tags=["Chat"])
app.include_router(ingest.router, tags=["Ingestion"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.log_level.lower()
    )
