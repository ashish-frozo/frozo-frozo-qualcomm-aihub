"""
Pipeline API routes.

Provides:
- POST /workspaces/{workspace_id}/pipelines - Create new pipeline
- GET /workspaces/{workspace_id}/pipelines - List all
- GET /workspaces/{workspace_id}/pipelines/{id} - Get details
- PUT /workspaces/{workspace_id}/pipelines/{id} - Update
- DELETE /workspaces/{workspace_id}/pipelines/{id} - Delete
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from edgegate.db import get_session
from edgegate.services.pipeline import (
    PipelineService,
    PipelineNotFoundError,
    PipelineValidationError,
    PromptPackRefError,
)
from edgegate.api.deps import CurrentUser, WorkspaceAdmin


router = APIRouter(tags=["Pipelines"])


# ============================================================================
# Schemas
# ============================================================================


class DeviceConfigSchema(BaseModel):
    """Device configuration in the matrix."""

    name: str
    enabled: bool = True


class PromptPackRefSchema(BaseModel):
    """Reference to a PromptPack."""

    promptpack_id: str
    version: str


class GateSchema(BaseModel):
    """Gate configuration."""

    metric: str
    operator: str  # lt, lte, gt, gte, eq
    threshold: float
    description: Optional[str] = None


class RunPolicySchema(BaseModel):
    """Run policy configuration."""

    warmup_runs: int = 1
    measurement_repeats: int = 3
    max_new_tokens: int = 128
    timeout_minutes: int = 20


class PipelineCreate(BaseModel):
    """Request body for creating a Pipeline."""

    name: str
    device_matrix: List[DeviceConfigSchema]
    promptpack_ref: PromptPackRefSchema
    gates: List[GateSchema]
    run_policy: RunPolicySchema = RunPolicySchema()


class PipelineUpdate(BaseModel):
    """Request body for updating a Pipeline."""

    name: Optional[str] = None
    device_matrix: Optional[List[DeviceConfigSchema]] = None
    promptpack_ref: Optional[PromptPackRefSchema] = None
    gates: Optional[List[GateSchema]] = None
    run_policy: Optional[RunPolicySchema] = None


class PipelineResponse(BaseModel):
    """Response with Pipeline info."""

    id: UUID
    name: str
    device_count: int
    gate_count: int
    promptpack_id: str
    promptpack_version: str
    created_at: datetime
    updated_at: datetime


class PipelineDetailResponse(BaseModel):
    """Response with full Pipeline details."""

    id: UUID
    name: str
    device_matrix: List[Dict[str, Any]]
    promptpack_ref: Dict[str, str]
    gates: List[Dict[str, Any]]
    run_policy: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Routes
# ============================================================================


@router.post(
    "/workspaces/{workspace_id}/pipelines",
    response_model=PipelineResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Pipeline",
)
async def create_pipeline(
    workspace: WorkspaceAdmin,
    request: PipelineCreate,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> PipelineResponse:
    """
    Create a new testing Pipeline.
    
    Pipelines define:
    - Device matrix (which devices to test on)
    - PromptPack reference (which test cases to use)
    - Gates (pass/fail criteria)
    - Run policy (warmup, repeats, timeout)
    
    Requires at least admin role.
    """
    service = PipelineService(session)

    try:
        result = await service.create(
            workspace=workspace,
            name=request.name,
            device_matrix=[d.model_dump() for d in request.device_matrix],
            promptpack_ref=request.promptpack_ref.model_dump(),
            gates=[g.model_dump() for g in request.gates],
            run_policy=request.run_policy.model_dump(),
            user=current_user,
        )
        return PipelineResponse(
            id=result.id,
            name=result.name,
            device_count=result.device_count,
            gate_count=result.gate_count,
            promptpack_id=result.promptpack_id,
            promptpack_version=result.promptpack_version,
            created_at=result.created_at,
            updated_at=result.updated_at,
        )
    except PipelineValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Validation failed", "issues": e.issues},
        )
    except PromptPackRefError as e:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail=e.message,
        )


@router.get(
    "/workspaces/{workspace_id}/pipelines",
    response_model=List[PipelineResponse],
    summary="List all Pipelines",
)
async def list_pipelines(
    workspace: WorkspaceAdmin,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> List[PipelineResponse]:
    """
    List all Pipelines in the workspace.
    
    Requires at least admin role.
    """
    service = PipelineService(session)
    results = await service.list_all(workspace)
    
    return [
        PipelineResponse(
            id=r.id,
            name=r.name,
            device_count=r.device_count,
            gate_count=r.gate_count,
            promptpack_id=r.promptpack_id,
            promptpack_version=r.promptpack_version,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in results
    ]


@router.get(
    "/workspaces/{workspace_id}/pipelines/{pipeline_id}",
    response_model=PipelineDetailResponse,
    summary="Get Pipeline details",
)
async def get_pipeline(
    workspace: WorkspaceAdmin,
    pipeline_id: UUID,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> PipelineDetailResponse:
    """
    Get full details of a Pipeline.
    
    Includes device matrix, gates, and run policy configuration.
    
    Requires at least admin role.
    """
    service = PipelineService(session)

    try:
        result = await service.get(
            workspace=workspace,
            pipeline_id=pipeline_id,
        )
        return PipelineDetailResponse(
            id=result.id,
            name=result.name,
            device_matrix=result.device_matrix,
            promptpack_ref=result.promptpack_ref,
            gates=result.gates,
            run_policy=result.run_policy,
            created_at=result.created_at,
            updated_at=result.updated_at,
        )
    except PipelineNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline {pipeline_id} not found",
        )


@router.put(
    "/workspaces/{workspace_id}/pipelines/{pipeline_id}",
    response_model=PipelineResponse,
    summary="Update a Pipeline",
)
async def update_pipeline(
    workspace: WorkspaceAdmin,
    pipeline_id: UUID,
    request: PipelineUpdate,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> PipelineResponse:
    """
    Update a Pipeline.
    
    All fields are optional. Only provided fields will be updated.
    
    Requires at least admin role.
    """
    service = PipelineService(session)

    try:
        result = await service.update(
            workspace=workspace,
            pipeline_id=pipeline_id,
            name=request.name,
            device_matrix=[d.model_dump() for d in request.device_matrix] if request.device_matrix else None,
            promptpack_ref=request.promptpack_ref.model_dump() if request.promptpack_ref else None,
            gates=[g.model_dump() for g in request.gates] if request.gates else None,
            run_policy=request.run_policy.model_dump() if request.run_policy else None,
            user=current_user,
        )
        return PipelineResponse(
            id=result.id,
            name=result.name,
            device_count=result.device_count,
            gate_count=result.gate_count,
            promptpack_id=result.promptpack_id,
            promptpack_version=result.promptpack_version,
            created_at=result.created_at,
            updated_at=result.updated_at,
        )
    except PipelineNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline {pipeline_id} not found",
        )
    except PipelineValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Validation failed", "issues": e.issues},
        )
    except PromptPackRefError as e:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail=e.message,
        )


@router.delete(
    "/workspaces/{workspace_id}/pipelines/{pipeline_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Pipeline",
)
async def delete_pipeline(
    workspace: WorkspaceAdmin,
    pipeline_id: UUID,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> None:
    """
    Delete a Pipeline.
    
    Requires at least admin role.
    """
    service = PipelineService(session)

    try:
        await service.delete(
            workspace=workspace,
            pipeline_id=pipeline_id,
            user=current_user,
        )
    except PipelineNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline {pipeline_id} not found",
        )
