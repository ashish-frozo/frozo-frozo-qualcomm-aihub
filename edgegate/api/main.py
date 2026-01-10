"""
FastAPI application entry point.

EdgeGate API - Edge GenAI Regression Gates for Snapdragon
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from edgegate.core import get_settings
from edgegate.db.session import close_db
from edgegate.api.routes import (
    auth_router,
    workspaces_router,
    integrations_router,
    capabilities_router,
    promptpacks_router,
    pipelines_router,
    runs_router,
    artifacts_router,
    ci_router,
    health_router,
)
from edgegate.api.middleware import RateLimitConfig, RateLimitMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    
    Handles startup and shutdown events.
    """
    # Startup
    settings = get_settings()
    print(f"Starting EdgeGate API in {settings.app_env} mode")
    
    # Validate required secrets in production
    if settings.app_env == "production":
        if not settings.jwt_secret_key or settings.jwt_secret_key == "":
            raise RuntimeError("JWT_SECRET_KEY is required in production")
        if not settings.edgegenai_master_key or settings.edgegenai_master_key == "":
            raise RuntimeError("EDGEGENAI_MASTER_KEY is required in production")
    
    yield
    
    # Shutdown
    await close_db()
    print("EdgeGate API shutdown complete")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()

    app = FastAPI(
        title="EdgeGate API",
        description="Edge GenAI Regression Gates for Snapdragon - AI Hub-Orchestrated",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Configure Rate Limiting
    rate_limit_rpm = int(os.environ.get("RATE_LIMIT_REQUESTS_PER_MINUTE", "60"))
    app.add_middleware(
        RateLimitMiddleware,
        config=RateLimitConfig(requests_per_minute=rate_limit_rpm),
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


    # Root route
    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "message": "Welcome to EdgeGate API",
            "docs": "/docs",
            "version": "0.1.0"
        }

    # Include routers
    app.include_router(health_router)
    app.include_router(auth_router, prefix="/v1")
    app.include_router(workspaces_router, prefix="/v1")
    app.include_router(integrations_router, prefix="/v1")
    app.include_router(capabilities_router, prefix="/v1")
    app.include_router(promptpacks_router, prefix="/v1")
    app.include_router(pipelines_router, prefix="/v1")
    app.include_router(runs_router, prefix="/v1")
    app.include_router(artifacts_router, prefix="/v1")
    app.include_router(ci_router, prefix="/v1")

    return app


# Create the application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "edgegate.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development,
    )
