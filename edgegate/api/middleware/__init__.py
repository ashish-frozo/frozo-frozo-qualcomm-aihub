"""
Middleware package for EdgeGate API.
"""

from edgegate.api.middleware.rate_limit import (
    RateLimitConfig,
    RateLimitMiddleware,
)

__all__ = [
    "RateLimitConfig",
    "RateLimitMiddleware",
]
