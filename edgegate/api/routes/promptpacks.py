"""
PromptPack API routes.

Provides:
- POST /workspaces/{workspace_id}/promptpacks - Create new version
- GET /workspaces/{workspace_id}/promptpacks - List all
- GET /workspaces/{workspace_id}/promptpacks/{id}/{version} - Get details
- PUT /workspaces/{workspace_id}/promptpacks/{id}/{version}/publish - Publish
- DELETE /workspaces/{workspace_id}/promptpacks/{id}/{version} - Delete
"""

from datetime import datetime
from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from edgegate.db import get_session
from edgegate.services.promptpack import (
    PromptPackService,
    PromptPackNotFoundError,
    PromptPackExistsError,
    PromptPackValidationError,
    PromptPackImmutableError,
)
from edgegate.api.deps import CurrentUser, WorkspaceAdmin


router = APIRouter(tags=["PromptPacks"])


# ============================================================================
# Schemas
# ============================================================================


class PromptPackCreate(BaseModel):
    """Request body for creating a PromptPack."""

    promptpack_id: str
    version: str
    content: Dict[str, Any]


class PromptPackResponse(BaseModel):
    """Response with PromptPack info."""

    id: UUID
    promptpack_id: str
    version: str
    sha256: str
    case_count: int
    published: bool
    created_at: datetime


class PromptPackDetailResponse(BaseModel):
    """Response with full PromptPack details."""

    id: UUID
    promptpack_id: str
    version: str
    sha256: str
    json_content: Dict[str, Any]
    published: bool
    created_at: datetime


class ValidationIssue(BaseModel):
    """Validation issue detail."""

    code: str
    message: str
    path: str


class ValidationErrorResponse(BaseModel):
    """Validation error response."""

    detail: str
    issues: List[ValidationIssue]


# ============================================================================
# Routes
# ============================================================================


@router.post(
    "/workspaces/{workspace_id}/promptpacks",
    response_model=PromptPackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new PromptPack version",
)
async def create_promptpack(
    workspace: WorkspaceAdmin,
    request: PromptPackCreate,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> PromptPackResponse:
    """
    Create a new PromptPack version.
    
    PromptPacks are immutable after creation. Each version is identified
    by the combination of promptpack_id and version string.
    
    Content is validated against the PromptPack schema and PRD limits.
    
    Requires at least admin role.
    """
    service = PromptPackService(session)

    try:
        result = await service.create(
            workspace=workspace,
            promptpack_id=request.promptpack_id,
            version=request.version,
            content=request.content,
            user=current_user,
        )
        return PromptPackResponse(
            id=result.id,
            promptpack_id=result.promptpack_id,
            version=result.version,
            sha256=result.sha256,
            case_count=result.case_count,
            published=result.published,
            created_at=result.created_at,
        )
    except PromptPackValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Validation failed", "issues": e.issues},
        )
    except PromptPackExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
        )


@router.get(
    "/workspaces/{workspace_id}/promptpacks",
    response_model=List[PromptPackResponse],
    summary="List all PromptPacks",
)
async def list_promptpacks(
    workspace: WorkspaceAdmin,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> List[PromptPackResponse]:
    """
    List all PromptPacks in the workspace.
    
    Returns all versions of all PromptPacks.
    
    Requires at least admin role.
    """
    service = PromptPackService(session)
    results = await service.list_all(workspace)
    
    return [
        PromptPackResponse(
            id=r.id,
            promptpack_id=r.promptpack_id,
            version=r.version,
            sha256=r.sha256,
            case_count=r.case_count,
            published=r.published,
            created_at=r.created_at,
        )
        for r in results
    ]


@router.get(
    "/workspaces/{workspace_id}/promptpacks/{promptpack_id}/{version}",
    response_model=PromptPackDetailResponse,
    summary="Get PromptPack details",
)
async def get_promptpack(
    workspace: WorkspaceAdmin,
    promptpack_id: str,
    version: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> PromptPackDetailResponse:
    """
    Get full details of a specific PromptPack version.
    
    Includes the complete JSON content.
    
    Requires at least admin role.
    """
    service = PromptPackService(session)

    try:
        result = await service.get(
            workspace=workspace,
            promptpack_id=promptpack_id,
            version=version,
        )
        return PromptPackDetailResponse(
            id=result.id,
            promptpack_id=result.promptpack_id,
            version=result.version,
            sha256=result.sha256,
            json_content=result.json_content,
            published=result.published,
            created_at=result.created_at,
        )
    except PromptPackNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PromptPack {promptpack_id}@{version} not found",
        )


@router.put(
    "/workspaces/{workspace_id}/promptpacks/{promptpack_id}/{version}/publish",
    response_model=PromptPackResponse,
    summary="Publish a PromptPack",
)
async def publish_promptpack(
    workspace: WorkspaceAdmin,
    promptpack_id: str,
    version: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> PromptPackResponse:
    """
    Publish a PromptPack version.
    
    Published PromptPacks can be referenced in Pipelines.
    Publishing is irreversible.
    
    Requires at least admin role.
    """
    service = PromptPackService(session)

    try:
        result = await service.publish(
            workspace=workspace,
            promptpack_id=promptpack_id,
            version=version,
            user=current_user,
        )
        return PromptPackResponse(
            id=result.id,
            promptpack_id=result.promptpack_id,
            version=result.version,
            sha256=result.sha256,
            case_count=result.case_count,
            published=result.published,
            created_at=result.created_at,
        )
    except PromptPackNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PromptPack {promptpack_id}@{version} not found",
        )


@router.delete(
    "/workspaces/{workspace_id}/promptpacks/{promptpack_id}/{version}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a PromptPack",
)
async def delete_promptpack(
    workspace: WorkspaceAdmin,
    promptpack_id: str,
    version: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> None:
    """
    Delete a PromptPack version.
    
    Only unpublished PromptPacks can be deleted.
    
    Requires at least admin role.
    """
    service = PromptPackService(session)

    try:
        await service.delete(
            workspace=workspace,
            promptpack_id=promptpack_id,
            version=version,
            user=current_user,
        )
    except PromptPackNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PromptPack {promptpack_id}@{version} not found",
        )
    except PromptPackImmutableError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete published PromptPack",
        )
