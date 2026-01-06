"""
Workspace API routes.

Provides:
- POST /workspaces - Create workspace
- GET /workspaces - List user's workspaces
- GET /workspaces/{id} - Get workspace details
- PUT /workspaces/{id} - Update workspace
- DELETE /workspaces/{id} - Delete workspace
- GET /workspaces/{id}/members - List members
- POST /workspaces/{id}/members - Add member
- PUT /workspaces/{id}/members/{user_id} - Update member role
- DELETE /workspaces/{id}/members/{user_id} - Remove member
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from edgegate.db import get_session, WorkspaceRole
from edgegate.db.models import User
from edgegate.services.workspace import (
    WorkspaceService,
    MembershipExistsError,
    CannotRemoveOwnerError,
    InsufficientPermissionsError,
)
from edgegate.services.auth import AuthService
from edgegate.api.deps import CurrentUser, WorkspaceViewer, WorkspaceAdmin, WorkspaceOwner


router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


# ============================================================================
# Schemas
# ============================================================================


class WorkspaceCreate(BaseModel):
    """Request body for workspace creation."""

    name: str


class WorkspaceUpdate(BaseModel):
    """Request body for workspace update."""

    name: str


class WorkspaceResponse(BaseModel):
    """Response with workspace details."""

    id: UUID
    name: str
    role: str  # User's role in this workspace

    class Config:
        from_attributes = True


class MemberCreate(BaseModel):
    """Request body for adding a member."""

    user_email: str
    role: WorkspaceRole


class MemberUpdate(BaseModel):
    """Request body for updating member role."""

    role: WorkspaceRole


class MemberResponse(BaseModel):
    """Response with member details."""

    user_id: UUID
    email: str
    role: str

    class Config:
        from_attributes = True


# ============================================================================
# Workspace CRUD Routes
# ============================================================================


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workspace",
)
async def create_workspace(
    request: WorkspaceCreate,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> WorkspaceResponse:
    """
    Create a new workspace.
    
    The current user automatically becomes the workspace owner.
    """
    workspace_service = WorkspaceService(session)
    workspace = await workspace_service.create_workspace(
        name=request.name,
        owner=current_user,
    )
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        role=WorkspaceRole.OWNER.value,
    )


@router.get(
    "",
    response_model=List[WorkspaceResponse],
    summary="List workspaces",
)
async def list_workspaces(
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> List[WorkspaceResponse]:
    """
    List all workspaces the current user is a member of.
    """
    workspace_service = WorkspaceService(session)
    workspaces = await workspace_service.list_workspaces(current_user)

    result = []
    for workspace in workspaces:
        role = await workspace_service.get_user_role(workspace.id, current_user)
        result.append(WorkspaceResponse(
            id=workspace.id,
            name=workspace.name,
            role=role.value if role else "unknown",
        ))
    return result


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Get workspace details",
)
async def get_workspace(
    workspace: WorkspaceViewer,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> WorkspaceResponse:
    """
    Get details of a specific workspace.
    
    Requires at least viewer role.
    """
    workspace_service = WorkspaceService(session)
    role = await workspace_service.get_user_role(workspace.id, current_user)
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        role=role.value if role else "unknown",
    )


@router.put(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Update workspace",
)
async def update_workspace(
    workspace: WorkspaceAdmin,
    request: WorkspaceUpdate,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> WorkspaceResponse:
    """
    Update workspace details.
    
    Requires at least admin role.
    """
    workspace_service = WorkspaceService(session)
    updated = await workspace_service.update_workspace(
        workspace_id=workspace.id,
        user=current_user,
        name=request.name,
    )
    role = await workspace_service.get_user_role(updated.id, current_user)
    return WorkspaceResponse(
        id=updated.id,
        name=updated.name,
        role=role.value if role else "unknown",
    )


@router.delete(
    "/{workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete workspace",
)
async def delete_workspace(
    workspace: WorkspaceOwner,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> None:
    """
    Delete a workspace and all its data.
    
    Requires owner role. This action is irreversible.
    """
    workspace_service = WorkspaceService(session)
    await workspace_service.delete_workspace(workspace.id, current_user)


# ============================================================================
# Member Management Routes
# ============================================================================


@router.get(
    "/{workspace_id}/members",
    response_model=List[MemberResponse],
    summary="List workspace members",
)
async def list_members(
    workspace: WorkspaceViewer,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> List[MemberResponse]:
    """
    List all members of a workspace.
    
    Requires at least viewer role.
    """
    workspace_service = WorkspaceService(session)
    members = await workspace_service.list_members(workspace.id, current_user)
    return [
        MemberResponse(
            user_id=m.user_id,
            email=m.user.email,
            role=m.role.value,
        )
        for m in members
    ]


@router.post(
    "/{workspace_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add workspace member",
)
async def add_member(
    workspace: WorkspaceAdmin,
    request: MemberCreate,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> MemberResponse:
    """
    Add a new member to the workspace.
    
    Requires at least admin role. Only owners can add other owners.
    """
    workspace_service = WorkspaceService(session)
    auth_service = AuthService(session)

    # Find user by email
    user = await auth_service._get_user_by_email(request.user_email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email {request.user_email} not found",
        )

    try:
        membership = await workspace_service.add_member(
            workspace_id=workspace.id,
            user_to_add=user,
            role=request.role,
            requesting_user=current_user,
        )
        return MemberResponse(
            user_id=membership.user_id,
            email=user.email,
            role=membership.role.value,
        )
    except MembershipExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this workspace",
        )
    except InsufficientPermissionsError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=e.message,
        )


@router.put(
    "/{workspace_id}/members/{user_id}",
    response_model=MemberResponse,
    summary="Update member role",
)
async def update_member_role(
    workspace: WorkspaceOwner,
    user_id: UUID,
    request: MemberUpdate,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> MemberResponse:
    """
    Update a member's role in the workspace.
    
    Requires owner role.
    """
    workspace_service = WorkspaceService(session)
    auth_service = AuthService(session)

    # Find target user
    user = await auth_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    try:
        membership = await workspace_service.update_member_role(
            workspace_id=workspace.id,
            user_to_update=user,
            new_role=request.role,
            requesting_user=current_user,
        )
        return MemberResponse(
            user_id=membership.user_id,
            email=user.email,
            role=membership.role.value,
        )
    except CannotRemoveOwnerError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the last owner from workspace",
        )


@router.delete(
    "/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove workspace member",
)
async def remove_member(
    workspace: WorkspaceOwner,
    user_id: UUID,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> None:
    """
    Remove a member from the workspace.
    
    Requires owner role.
    """
    workspace_service = WorkspaceService(session)
    auth_service = AuthService(session)

    # Find target user
    user = await auth_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    try:
        await workspace_service.remove_member(
            workspace_id=workspace.id,
            user_to_remove=user,
            requesting_user=current_user,
        )
    except CannotRemoveOwnerError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the last owner from workspace",
        )
