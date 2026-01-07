"""
Artifacts API routes.

Provides:
- POST /workspaces/{workspace_id}/artifacts - Upload artifact
- GET /workspaces/{workspace_id}/artifacts/{id} - Get artifact info
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from edgegate.db import get_session, ArtifactKind
from edgegate.services.artifact import (
    ArtifactService,
    ArtifactNotFoundError,
    ArtifactSizeLimitError,
)
from edgegate.api.deps import CurrentUser, WorkspaceAdmin


router = APIRouter(tags=["Artifacts"])


# ============================================================================
# Schemas
# ============================================================================


class ArtifactResponse(BaseModel):
    """Response with Artifact info."""

    id: UUID
    kind: str
    sha256: str
    size_bytes: int
    original_filename: Optional[str]
    storage_url: str
    created_at: datetime
    expires_at: Optional[datetime]


# ============================================================================
# Routes
# ============================================================================


@router.post(
    "/workspaces/{workspace_id}/artifacts",
    response_model=ArtifactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an artifact",
)
async def upload_artifact(
    workspace: WorkspaceAdmin,
    current_user: CurrentUser,
    file: UploadFile = File(..., description="Artifact file"),
    kind: str = Form("model", description="Artifact type: model, bundle, other"),
    session: AsyncSession = Depends(get_session),
) -> ArtifactResponse:
    """
    Upload an artifact (model, bundle, etc.).
    
    Artifacts are content-addressed by SHA-256. Uploading the same
    content again will return the existing artifact.
    
    Requirements:
    - Model artifacts: max 2 GB
    - Bundle artifacts: max 10 MB
    
    Requires at least admin role.
    """
    # Map kind string to enum
    kind_map = {
        "model": ArtifactKind.MODEL,
        "bundle": ArtifactKind.BUNDLE,
        "probe_raw": ArtifactKind.PROBE_RAW,
        "capabilities": ArtifactKind.CAPABILITIES,
        "metric_mapping": ArtifactKind.METRIC_MAPPING,
        "promptpack": ArtifactKind.PROMPTPACK,
        "other": ArtifactKind.OTHER,
    }
    artifact_kind = kind_map.get(kind, ArtifactKind.OTHER)
    
    # Read file content
    content = await file.read()
    
    service = ArtifactService(session)

    try:
        result = await service.create(
            workspace=workspace,
            kind=artifact_kind,
            content=content,
            original_filename=file.filename,
            user=current_user,
        )
        return ArtifactResponse(
            id=result.id,
            kind=result.kind.value,
            sha256=result.sha256,
            size_bytes=result.size_bytes,
            original_filename=result.original_filename,
            storage_url=result.storage_url,
            created_at=result.created_at,
            expires_at=result.expires_at,
        )
    except ArtifactSizeLimitError as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=e.message,
        )


@router.get(
    "/workspaces/{workspace_id}/artifacts",
    response_model=List[ArtifactResponse],
    summary="List artifacts",
)
async def list_artifacts(
    workspace: WorkspaceAdmin,
    current_user: CurrentUser,
    kind: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
) -> List[ArtifactResponse]:
    """
    List artifacts in the workspace.
    
    Can be filtered by artifact kind.
    
    Requires at least admin role.
    """
    service = ArtifactService(session)
    
    # Map kind filter if provided
    kind_filter = None
    if kind:
        kind_map = {
            "model": ArtifactKind.MODEL,
            "bundle": ArtifactKind.BUNDLE,
            "probe_raw": ArtifactKind.PROBE_RAW,
            "capabilities": ArtifactKind.CAPABILITIES,
            "metric_mapping": ArtifactKind.METRIC_MAPPING,
            "promptpack": ArtifactKind.PROMPTPACK,
            "other": ArtifactKind.OTHER,
        }
        kind_filter = kind_map.get(kind)
    
    results = await service.list_all(workspace=workspace, kind=kind_filter)
    
    return [
        ArtifactResponse(
            id=r.id,
            kind=r.kind.value,
            sha256=r.sha256,
            size_bytes=r.size_bytes,
            original_filename=r.original_filename,
            storage_url=r.storage_url,
            created_at=r.created_at,
            expires_at=r.expires_at,
        )
        for r in results
    ]


@router.get(
    "/workspaces/{workspace_id}/artifacts/{artifact_id}",
    response_model=ArtifactResponse,
    summary="Get artifact info",
)
async def get_artifact(
    workspace: WorkspaceAdmin,
    artifact_id: UUID,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> ArtifactResponse:
    """
    Get artifact metadata.
    
    Requires at least admin role.
    """
    service = ArtifactService(session)

    try:
        result = await service.get(
            workspace=workspace,
            artifact_id=artifact_id,
        )
        return ArtifactResponse(
            id=result.id,
            kind=result.kind.value,
            sha256=result.sha256,
            size_bytes=result.size_bytes,
            original_filename=result.original_filename,
            storage_url=result.storage_url,
            created_at=result.created_at,
            expires_at=result.expires_at,
        )
    except ArtifactNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact {artifact_id} not found",
        )
