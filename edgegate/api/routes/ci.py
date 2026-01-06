"""
CI webhook API routes.

Provides:
- POST /ci/github/run - Trigger a run from GitHub Actions
- POST /ci/webhook - Generic CI webhook
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from edgegate.db import get_session, RunTrigger
from edgegate.api.ci_auth import get_ci_workspace, CIWorkspace
from edgegate.services.run import RunService, PipelineNotFoundError, ArtifactNotFoundError


router = APIRouter(tags=["CI"])


# ============================================================================
# Schemas
# ============================================================================


class CIRunRequest(BaseModel):
    """Request body for CI-triggered run."""

    pipeline_id: UUID
    model_artifact_id: UUID
    commit_sha: Optional[str] = None
    branch: Optional[str] = None
    pull_request: Optional[int] = None
    workflow_run_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CIRunResponse(BaseModel):
    """Response for CI-triggered run."""

    run_id: UUID
    status: str
    pipeline_id: UUID
    message: str


class CIStatusResponse(BaseModel):
    """Response for CI status check."""

    status: str
    workspace_id: UUID
    message: str


# ============================================================================
# Routes
# ============================================================================


@router.post(
    "/ci/github/run",
    response_model=CIRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a run from GitHub Actions",
)
async def github_trigger_run(
    request: CIRunRequest,
    workspace: CIWorkspace = Depends(get_ci_workspace),
    session: AsyncSession = Depends(get_session),
) -> CIRunResponse:
    """
    Trigger a regression test run from GitHub Actions.
    
    Requires HMAC authentication headers:
    - X-EdgeGate-Workspace: workspace UUID
    - X-EdgeGate-Timestamp: ISO8601 timestamp
    - X-EdgeGate-Nonce: unique request nonce
    - X-EdgeGate-Signature: HMAC-SHA256 signature
    
    The signature is computed over: timestamp\\nnonce\\nbody
    """
    service = RunService(session)

    try:
        result = await service.create(
            workspace=workspace,
            pipeline_id=request.pipeline_id,
            model_artifact_id=request.model_artifact_id,
            trigger=RunTrigger.CI,
            user=None,  # CI-triggered, no user
        )
        
        # In production, trigger Celery task
        # from edgegate.tasks import execute_run_pipeline
        # execute_run_pipeline(str(result.id), str(workspace.id))
        
        return CIRunResponse(
            run_id=result.id,
            status="queued",
            pipeline_id=result.pipeline_id,
            message="Run queued successfully",
        )
    except PipelineNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        )
    except ArtifactNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        )


@router.post(
    "/ci/webhook",
    response_model=CIRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generic CI webhook",
)
async def ci_webhook(
    request: CIRunRequest,
    workspace: CIWorkspace = Depends(get_ci_workspace),
    session: AsyncSession = Depends(get_session),
) -> CIRunResponse:
    """
    Generic CI webhook for triggering runs.
    
    Works with any CI system that can make HTTP requests with HMAC signatures.
    
    Requires HMAC authentication headers:
    - X-EdgeGate-Workspace: workspace UUID
    - X-EdgeGate-Timestamp: ISO8601 timestamp
    - X-EdgeGate-Nonce: unique request nonce
    - X-EdgeGate-Signature: HMAC-SHA256 signature
    """
    service = RunService(session)

    try:
        result = await service.create(
            workspace=workspace,
            pipeline_id=request.pipeline_id,
            model_artifact_id=request.model_artifact_id,
            trigger=RunTrigger.CI,
            user=None,
        )
        
        return CIRunResponse(
            run_id=result.id,
            status="queued",
            pipeline_id=result.pipeline_id,
            message="Run queued successfully",
        )
    except PipelineNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        )
    except ArtifactNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        )


@router.get(
    "/ci/status",
    response_model=CIStatusResponse,
    summary="Check CI authentication status",
)
async def ci_status(
    workspace: CIWorkspace = Depends(get_ci_workspace),
) -> CIStatusResponse:
    """
    Check if CI authentication is working correctly.
    
    Useful for testing webhook configuration.
    """
    return CIStatusResponse(
        status="ok",
        workspace_id=workspace.id,
        message="CI authentication successful",
    )
