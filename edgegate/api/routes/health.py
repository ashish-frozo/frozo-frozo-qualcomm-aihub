"""
Health check routes.
"""

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health check")
async def health_check():
    """
    Simple health check endpoint.
    
    Returns OK status when service is running.
    """
    return {"status": "ok"}


@router.get("/ready", summary="Readiness check")
async def readiness_check():
    """
    Readiness check endpoint.
    
    Returns OK when service is ready to accept requests.
    TODO: Add database and Redis connectivity checks.
    """
    return {"status": "ready"}
