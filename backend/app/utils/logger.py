"""Logging configuration and utilities"""

import logging
import sys
import time
from typing import Any, Dict, Optional
from functools import wraps
import json
from datetime import datetime

from backend.app.core.config import settings


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present
        if hasattr(record, "extra"):
            log_data.update(record.extra)
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


def setup_logger(name: str) -> logging.Logger:
    """Set up a logger with structured formatting"""
    logger = logging.getLogger(name)
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Use simple format for development, structured for production
    if settings.log_level.upper() == "DEBUG":
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    else:
        formatter = StructuredFormatter()
    
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


def log_execution_time(logger: logging.Logger):
    """Decorator to log function execution time"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000  # ms
                logger.info(
                    f"{func.__name__} executed",
                    extra={
                        "function": func.__name__,
                        "execution_time_ms": round(execution_time, 2),
                        "status": "success"
                    }
                )
                return result
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000  # ms
                logger.error(
                    f"{func.__name__} failed",
                    extra={
                        "function": func.__name__,
                        "execution_time_ms": round(execution_time, 2),
                        "status": "error",
                        "error": str(e)
                    }
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000  # ms
                logger.info(
                    f"{func.__name__} executed",
                    extra={
                        "function": func.__name__,
                        "execution_time_ms": round(execution_time, 2),
                        "status": "success"
                    }
                )
                return result
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000  # ms
                logger.error(
                    f"{func.__name__} failed",
                    extra={
                        "function": func.__name__,
                        "execution_time_ms": round(execution_time, 2),
                        "status": "error",
                        "error": str(e)
                    }
                )
                raise
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def log_query_metrics(
    logger: logging.Logger,
    session_id: str,
    query: str,
    retrieved_chunks: int,
    avg_similarity: float,
    latency_ms: float,
    confidence: str
):
    """Log metrics for a query"""
    logger.info(
        "Query processed",
        extra={
            "session_id": session_id,
            "query_length": len(query),
            "retrieved_chunks": retrieved_chunks,
            "avg_similarity": round(avg_similarity, 3),
            "latency_ms": round(latency_ms, 2),
            "confidence": confidence,
            "event_type": "query_metrics"
        }
    )


def log_ingestion_metrics(
    logger: logging.Logger,
    total_chunks: int,
    duration_seconds: float,
    success: bool,
    error: Optional[str] = None
):
    """Log metrics for document ingestion"""
    logger.info(
        "Document ingestion completed",
        extra={
            "total_chunks": total_chunks,
            "duration_seconds": round(duration_seconds, 2),
            "success": success,
            "error": error,
            "event_type": "ingestion_metrics"
        }
    )


# Create global logger instances
app_logger = setup_logger("travel_assist_bot")
api_logger = setup_logger("travel_assist_bot.api")
service_logger = setup_logger("travel_assist_bot.services")
