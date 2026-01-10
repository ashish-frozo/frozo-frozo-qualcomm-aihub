"""
Logging configuration for EdgeGate.

Provides structured logging with JSON output in production
and human-readable output in development.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


def setup_logging(
    log_level: str = "INFO",
    json_format: bool = True,
    app_env: str = "production",
) -> None:
    """
    Configure structured logging for the application.
    
    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_format: If True, output JSON logs. If False, output colored console logs.
        app_env: Application environment (development, staging, production).
    """
    # Determine if we should use JSON format
    use_json = json_format and app_env != "development"
    
    # Configure shared processors
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    
    if use_json:
        # Production: JSON output
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
        
        # Configure stdlib logging to also use JSON
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=getattr(logging, log_level.upper()),
        )
    else:
        # Development: colored console output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
        
        # Configure stdlib logging for development
        logging.basicConfig(
            format="%(levelname)s %(name)s: %(message)s",
            stream=sys.stdout,
            level=getattr(logging, log_level.upper()),
        )
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Reduce noise from third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Optional logger name. If not provided, uses caller's module name.
        
    Returns:
        Configured structlog logger.
    """
    return structlog.get_logger(name)


# Convenience functions for logging with context
def log_request(
    logger: structlog.BoundLogger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    **extra: Any,
) -> None:
    """Log an HTTP request with standard fields."""
    logger.info(
        "http_request",
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=round(duration_ms, 2),
        **extra,
    )


def log_celery_task(
    logger: structlog.BoundLogger,
    task_name: str,
    task_id: str,
    status: str,
    duration_ms: float | None = None,
    **extra: Any,
) -> None:
    """Log a Celery task execution."""
    logger.info(
        "celery_task",
        task_name=task_name,
        task_id=task_id,
        status=status,
        duration_ms=round(duration_ms, 2) if duration_ms else None,
        **extra,
    )


def log_aihub_job(
    logger: structlog.BoundLogger,
    job_id: str,
    job_type: str,
    status: str,
    device: str | None = None,
    **extra: Any,
) -> None:
    """Log an AI Hub job event."""
    logger.info(
        "aihub_job",
        job_id=job_id,
        job_type=job_type,
        status=status,
        device=device,
        **extra,
    )
