"""
Sentry error tracking configuration for EdgeGate.

Initializes Sentry SDK with proper configuration for FastAPI and Celery.
"""

from __future__ import annotations

import os
from typing import Any

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration


def init_sentry(
    dsn: str | None = None,
    environment: str = "development",
    release: str | None = None,
    traces_sample_rate: float = 0.1,
    profiles_sample_rate: float = 0.1,
) -> bool:
    """
    Initialize Sentry error tracking.
    
    Args:
        dsn: Sentry DSN. If not provided, reads from SENTRY_DSN env var.
        environment: Application environment (development, staging, production).
        release: Application release/version string.
        traces_sample_rate: Sample rate for performance monitoring (0.0 to 1.0).
        profiles_sample_rate: Sample rate for profiling (0.0 to 1.0).
        
    Returns:
        True if Sentry was initialized, False if skipped (no DSN).
    """
    # Get DSN from argument or environment
    sentry_dsn = dsn or os.environ.get("SENTRY_DSN")
    
    if not sentry_dsn:
        # Skip Sentry initialization if no DSN provided
        print("Sentry DSN not configured - error tracking disabled")
        return False
    
    # Don't send errors from development by default
    if environment == "development" and not os.environ.get("SENTRY_FORCE_ENABLE"):
        print("Sentry disabled in development (set SENTRY_FORCE_ENABLE=1 to enable)")
        return False
    
    # Configure Sentry
    sentry_sdk.init(
        dsn=sentry_dsn,
        environment=environment,
        release=release or os.environ.get("RAILWAY_GIT_COMMIT_SHA", "development"),
        
        # Integrations
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            CeleryIntegration(),
            SqlalchemyIntegration(),
            LoggingIntegration(
                level=None,  # Capture all breadcrumbs
                event_level=40,  # Only send ERROR and above as events
            ),
        ],
        
        # Performance Monitoring
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=profiles_sample_rate,
        
        # Additional settings
        send_default_pii=False,  # Don't send PII by default
        attach_stacktrace=True,
        
        # Filter out noisy errors
        before_send=_filter_events,
    )
    
    print(f"Sentry initialized for environment: {environment}")
    return True


def _filter_events(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """
    Filter Sentry events before sending.
    
    Filters out common non-actionable errors.
    """
    # Get exception info if available
    if "exc_info" in hint:
        exc_type, exc_value, _ = hint["exc_info"]
        
        # Filter out common HTTP errors that aren't bugs
        ignored_exceptions = [
            "ConnectionResetError",
            "BrokenPipeError",
            "ClientDisconnect",
        ]
        
        if exc_type.__name__ in ignored_exceptions:
            return None
        
        # Filter out 404 errors (not bugs)
        if "HTTPException" in exc_type.__name__:
            if hasattr(exc_value, "status_code") and exc_value.status_code == 404:
                return None
    
    return event


def capture_exception(error: Exception, **context: Any) -> str | None:
    """
    Capture an exception to Sentry with additional context.
    
    Args:
        error: The exception to capture.
        **context: Additional context to attach to the event.
        
    Returns:
        Event ID if captured, None otherwise.
    """
    with sentry_sdk.push_scope() as scope:
        for key, value in context.items():
            scope.set_extra(key, value)
        return sentry_sdk.capture_exception(error)


def capture_message(message: str, level: str = "info", **context: Any) -> str | None:
    """
    Capture a message to Sentry.
    
    Args:
        message: The message to capture.
        level: Message level (debug, info, warning, error, fatal).
        **context: Additional context to attach to the event.
        
    Returns:
        Event ID if captured, None otherwise.
    """
    with sentry_sdk.push_scope() as scope:
        for key, value in context.items():
            scope.set_extra(key, value)
        return sentry_sdk.capture_message(message, level=level)


def set_user(user_id: str, email: str | None = None, **extra: Any) -> None:
    """Set the current user context for Sentry events."""
    sentry_sdk.set_user({
        "id": user_id,
        "email": email,
        **extra,
    })


def set_tag(key: str, value: str) -> None:
    """Set a tag that will be attached to all events in this scope."""
    sentry_sdk.set_tag(key, value)
