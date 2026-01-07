"""
Runs API routes.

Provides:
- POST /workspaces/{workspace_id}/runs - Create new run
- GET /workspaces/{workspace_id}/runs - List runs
- GET /workspaces/{workspace_id}/runs/{id} - Get run details
- GET /workspaces/{workspace_id}/runs/{id}/bundle - Get evidence bundle
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from edgegate.db import get_session, RunStatus, RunTrigger
from edgegate.services.run import (
    RunService,
    RunNotFoundError,
    PipelineNotFoundError,
    ArtifactNotFoundError,
)
from edgegate.api.deps import CurrentUser, WorkspaceAdmin


router = APIRouter(tags=["Runs"])


# ============================================================================
# Schemas
# ============================================================================


class RunCreate(BaseModel):
    """Request body for creating a Run."""

    pipeline_id: UUID
    model_artifact_id: Optional[UUID] = None  # Optional for manual runs
    trigger: str = "manual"  # manual, ci, scheduled


class RunResponse(BaseModel):
    """Response with Run info."""

    id: UUID
    pipeline_id: UUID
    status: str
    trigger: str
    created_at: datetime
    updated_at: datetime


class RunDetailResponse(BaseModel):
    """Response with full Run details."""

    id: UUID
    pipeline_id: UUID
    pipeline_name: str
    status: str
    trigger: str
    model_artifact_id: UUID
    normalized_metrics: Optional[Dict[str, Any]]
    gates_eval: Optional[Dict[str, Any]]
    bundle_artifact_id: Optional[UUID]
    error_code: Optional[str]
    error_detail: Optional[str]
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Routes
# ============================================================================


@router.post(
    "/workspaces/{workspace_id}/runs",
    response_model=RunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a new run",
)
async def create_run(
    workspace: WorkspaceAdmin,
    request: RunCreate,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> RunResponse:
    """
    Create and queue a new test run.
    
    The run will be executed asynchronously. Poll the run status
    endpoint to track progress.
    
    Requires at least admin role.
    """
    service = RunService(session)

    # Map trigger string to enum
    trigger_map = {
        "manual": RunTrigger.MANUAL,
        "ci": RunTrigger.CI,
        "scheduled": RunTrigger.SCHEDULED,
    }
    trigger = trigger_map.get(request.trigger, RunTrigger.MANUAL)

    try:
        result = await service.create(
            workspace=workspace,
            pipeline_id=request.pipeline_id,
            model_artifact_id=request.model_artifact_id,
            trigger=trigger,
            user=current_user,
        )
        
        # Trigger Celery task
        from edgegate.tasks import execute_run_pipeline
        execute_run_pipeline(str(result.id), str(workspace.id))
        
        return RunResponse(
            id=result.id,
            pipeline_id=result.pipeline_id,
            status=result.status.value,
            trigger=result.trigger.value,
            created_at=result.created_at,
            updated_at=result.updated_at,
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
    "/workspaces/{workspace_id}/runs",
    response_model=List[RunResponse],
    summary="List runs",
)
async def list_runs(
    workspace: WorkspaceAdmin,
    current_user: CurrentUser,
    pipeline_id: Optional[UUID] = Query(default=None, description="Filter by pipeline"),
    limit: int = Query(default=50, le=100, description="Maximum results"),
    session: AsyncSession = Depends(get_session),
) -> List[RunResponse]:
    """
    List runs in the workspace.
    
    Can be filtered by pipeline ID.
    
    Requires at least admin role.
    """
    service = RunService(session)
    results = await service.list_all(
        workspace=workspace,
        pipeline_id=pipeline_id,
        limit=limit,
    )
    
    return [
        RunResponse(
            id=r.id,
            pipeline_id=r.pipeline_id,
            status=r.status.value,
            trigger=r.trigger.value,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in results
    ]


@router.get(
    "/workspaces/{workspace_id}/runs/{run_id}",
    response_model=RunDetailResponse,
    summary="Get run details",
)
async def get_run(
    workspace: WorkspaceAdmin,
    run_id: UUID,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> RunDetailResponse:
    """
    Get full details of a run.
    
    Includes metrics, gates evaluation, and error info.
    
    Requires at least admin role.
    """
    service = RunService(session)

    try:
        result = await service.get(
            workspace=workspace,
            run_id=run_id,
        )
        return RunDetailResponse(
            id=result.id,
            pipeline_id=result.pipeline_id,
            pipeline_name=result.pipeline_name,
            status=result.status.value,
            trigger=result.trigger.value,
            model_artifact_id=result.model_artifact_id,
            normalized_metrics=result.normalized_metrics,
            gates_eval=result.gates_eval,
            bundle_artifact_id=result.bundle_artifact_id,
            error_code=result.error_code,
            error_detail=result.error_detail,
            created_at=result.created_at,
            updated_at=result.updated_at,
        )
    except RunNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )


@router.get(
    "/workspaces/{workspace_id}/runs/{run_id}/bundle",
    summary="Get evidence bundle",
)
async def get_run_bundle(
    workspace: WorkspaceAdmin,
    run_id: UUID,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Get the evidence bundle for a completed run.
    
    The bundle contains the signed summary and all metrics.
    Only available for PASSED or FAILED runs.
    
    Requires at least admin role.
    """
    service = RunService(session)

    try:
        result = await service.get(
            workspace=workspace,
            run_id=run_id,
        )
        
        if result.status not in [RunStatus.PASSED, RunStatus.FAILED]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Evidence bundle not available for {result.status.value} runs",
            )
        
        if not result.bundle_artifact_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence bundle not found for this run",
            )
        
        # In production, retrieve bundle from artifact storage
        # For now, return the available data
        return {
            "run_id": str(result.id),
            "status": result.status.value,
            "pipeline_id": str(result.pipeline_id),
            "pipeline_name": result.pipeline_name,
            "normalized_metrics": result.normalized_metrics,
            "gates_eval": result.gates_eval,
            "bundle_artifact_id": str(result.bundle_artifact_id),
        }
        
    except RunNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )
