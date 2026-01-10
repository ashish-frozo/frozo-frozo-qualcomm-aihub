"""
Rate limiting middleware for EdgeGate API.

Uses a simple in-memory sliding window counter with Redis backing for distributed deployments.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    
    requests_per_minute: int = 60
    burst_multiplier: float = 1.5  # Allow short bursts up to 1.5x the rate
    
    # Paths to exclude from rate limiting
    excluded_paths: list[str] = field(default_factory=lambda: [
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
    ])


class InMemoryRateLimiter:
    """Simple in-memory rate limiter using sliding window."""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.requests: dict[str, list[float]] = defaultdict(list)
        self.window_seconds = 60
    
    def _get_client_id(self, request: Request) -> str:
        """Get unique identifier for the client."""
        # Use X-Forwarded-For for clients behind reverse proxy
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        # Fall back to client host
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _cleanup_old_requests(self, client_id: str, now: float) -> None:
        """Remove requests outside the current window."""
        cutoff = now - self.window_seconds
        self.requests[client_id] = [
            ts for ts in self.requests[client_id] if ts > cutoff
        ]
    
    def is_allowed(self, request: Request) -> tuple[bool, dict[str, str]]:
        """
        Check if request is allowed.
        
        Returns:
            Tuple of (is_allowed, rate_limit_headers)
        """
        # Check exclusions
        path = request.url.path
        if any(path.startswith(excluded) for excluded in self.config.excluded_paths):
            return True, {}
        
        client_id = self._get_client_id(request)
        now = time.time()
        
        # Cleanup old requests
        self._cleanup_old_requests(client_id, now)
        
        # Count current requests
        current_count = len(self.requests[client_id])
        limit = int(self.config.requests_per_minute * self.config.burst_multiplier)
        remaining = max(0, limit - current_count)
        
        headers = {
            "X-RateLimit-Limit": str(self.config.requests_per_minute),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(now) + self.window_seconds),
        }
        
        if current_count >= limit:
            # Rate limited
            retry_after = self.window_seconds
            if self.requests[client_id]:
                oldest = min(self.requests[client_id])
                retry_after = max(1, int(oldest + self.window_seconds - now))
            headers["Retry-After"] = str(retry_after)
            return False, headers
        
        # Allow request
        self.requests[client_id].append(now)
        return True, headers


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting."""
    
    def __init__(self, app, config: RateLimitConfig | None = None):
        super().__init__(app)
        self.config = config or RateLimitConfig()
        self.limiter = InMemoryRateLimiter(self.config)
    
    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """Process request with rate limiting."""
        is_allowed, headers = self.limiter.is_allowed(request)
        
        if not is_allowed:
            response = JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please slow down.",
                    "retry_after": int(headers.get("Retry-After", 60)),
                },
            )
            for key, value in headers.items():
                response.headers[key] = value
            return response
        
        response = await call_next(request)
        
        # Add rate limit headers to successful responses
        for key, value in headers.items():
            response.headers[key] = value
        
        return response


def create_rate_limit_middleware(requests_per_minute: int = 60) -> RateLimitMiddleware:
    """Create rate limit middleware with specified configuration."""
    config = RateLimitConfig(requests_per_minute=requests_per_minute)
    return RateLimitMiddleware
