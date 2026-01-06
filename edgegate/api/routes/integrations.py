"""
Integration API routes.

Provides:
- POST /workspaces/{workspace_id}/integrations/qaihub - Connect AI Hub
- GET /workspaces/{workspace_id}/integrations/qaihub - Get integration info
- PUT /workspaces/{workspace_id}/integrations/qaihub/rotate - Rotate token
- PUT /workspaces/{workspace_id}/integrations/qaihub/disable - Disable
- PUT /workspaces/{workspace_id}/integrations/qaihub/enable - Enable
- DELETE /workspaces/{workspace_id}/integrations/qaihub - Delete
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from edgegate.db import get_session, IntegrationProvider, IntegrationStatus
from edgegate.core import get_settings
from edgegate.core.security import LocalKeyManagementService
from edgegate.services.integration import (
    IntegrationService,
    IntegrationNotFoundError,
    IntegrationExistsError,
)
from edgegate.api.deps import CurrentUser, WorkspaceAdmin, WorkspaceOwner


router = APIRouter(tags=["Integrations"])


# ============================================================================
# Schemas
# ============================================================================


class ConnectRequest(BaseModel):
    """Request body for connecting an integration."""

    token: SecretStr


class IntegrationResponse(BaseModel):
    """Response with integration details."""

    id: UUID
    provider: str
    status: str
    token_last4: str
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Helper to get KMS
# ============================================================================


def get_kms() -> LocalKeyManagementService:
    """Get the key management service."""
    settings = get_settings()
    return LocalKeyManagementService(
        master_key_b64=settings.edgegenai_master_key,
        signing_keys_path=settings.signing_keys_dir,
    )


# ============================================================================
# Routes
# ============================================================================


@router.post(
    "/workspaces/{workspace_id}/integrations/qaihub",
    response_model=IntegrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect AI Hub integration",
)
async def connect_qaihub(
    workspace: WorkspaceAdmin,
    request: ConnectRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> IntegrationResponse:
    """
    Connect Qualcomm AI Hub to the workspace.
    
    The API token will be encrypted using envelope encryption
    and stored securely. Only the last 4 characters are visible.
    
    Requires at least admin role.
    """
    try:
        kms = get_kms()
        service = IntegrationService(session, kms)
        
        integration = await service.connect(
            workspace=workspace,
            provider=IntegrationProvider.QAIHUB,
            token=request.token.get_secret_value(),
            user=current_user,
        )
        
        return IntegrationResponse(
            id=integration.id,
            provider=integration.provider.value,
            status=integration.status.value,
            token_last4=integration.token_last4,
            created_at=integration.created_at,
            updated_at=integration.updated_at,
        )
    except IntegrationExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="AI Hub integration already exists. Use rotate to update the token.",
        )


@router.get(
    "/workspaces/{workspace_id}/integrations/qaihub",
    response_model=IntegrationResponse,
    summary="Get AI Hub integration",
)
async def get_qaihub(
    workspace: WorkspaceAdmin,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> IntegrationResponse:
    """
    Get AI Hub integration details.
    
    Returns integration status and token last 4 characters.
    The full token is never exposed via API.
    
    Requires at least admin role.
    """
    try:
        kms = get_kms()
        service = IntegrationService(session, kms)
        
        integration = await service.get_integration(
            workspace=workspace,
            provider=IntegrationProvider.QAIHUB,
        )
        
        return IntegrationResponse(
            id=integration.id,
            provider=integration.provider.value,
            status=integration.status.value,
            token_last4=integration.token_last4,
            created_at=integration.created_at,
            updated_at=integration.updated_at,
        )
    except IntegrationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI Hub integration not found",
        )


@router.put(
    "/workspaces/{workspace_id}/integrations/qaihub/rotate",
    response_model=IntegrationResponse,
    summary="Rotate AI Hub token",
)
async def rotate_qaihub(
    workspace: WorkspaceOwner,
    request: ConnectRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> IntegrationResponse:
    """
    Rotate the AI Hub API token.
    
    The old token is replaced with the new one.
    If integration was disabled, it will be re-enabled.
    
    Requires owner role.
    """
    try:
        kms = get_kms()
        service = IntegrationService(session, kms)
        
        integration = await service.rotate(
            workspace=workspace,
            provider=IntegrationProvider.QAIHUB,
            new_token=request.token.get_secret_value(),
            user=current_user,
        )
        
        return IntegrationResponse(
            id=integration.id,
            provider=integration.provider.value,
            status=integration.status.value,
            token_last4=integration.token_last4,
            created_at=integration.created_at,
            updated_at=integration.updated_at,
        )
    except IntegrationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI Hub integration not found",
        )


@router.put(
    "/workspaces/{workspace_id}/integrations/qaihub/disable",
    response_model=IntegrationResponse,
    summary="Disable AI Hub integration",
)
async def disable_qaihub(
    workspace: WorkspaceOwner,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> IntegrationResponse:
    """
    Disable the AI Hub integration.
    
    The token is preserved but cannot be used until re-enabled.
    
    Requires owner role.
    """
    try:
        kms = get_kms()
        service = IntegrationService(session, kms)
        
        integration = await service.disable(
            workspace=workspace,
            provider=IntegrationProvider.QAIHUB,
            user=current_user,
        )
        
        return IntegrationResponse(
            id=integration.id,
            provider=integration.provider.value,
            status=integration.status.value,
            token_last4=integration.token_last4,
            created_at=integration.created_at,
            updated_at=integration.updated_at,
        )
    except IntegrationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI Hub integration not found",
        )


@router.put(
    "/workspaces/{workspace_id}/integrations/qaihub/enable",
    response_model=IntegrationResponse,
    summary="Enable AI Hub integration",
)
async def enable_qaihub(
    workspace: WorkspaceOwner,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> IntegrationResponse:
    """
    Re-enable the AI Hub integration.
    
    Requires owner role.
    """
    try:
        kms = get_kms()
        service = IntegrationService(session, kms)
        
        integration = await service.enable(
            workspace=workspace,
            provider=IntegrationProvider.QAIHUB,
            user=current_user,
        )
        
        return IntegrationResponse(
            id=integration.id,
            provider=integration.provider.value,
            status=integration.status.value,
            token_last4=integration.token_last4,
            created_at=integration.created_at,
            updated_at=integration.updated_at,
        )
    except IntegrationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI Hub integration not found",
        )


@router.delete(
    "/workspaces/{workspace_id}/integrations/qaihub",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete AI Hub integration",
)
async def delete_qaihub(
    workspace: WorkspaceOwner,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> None:
    """
    Delete the AI Hub integration completely.
    
    The encrypted token is permanently deleted.
    
    Requires owner role.
    """
    try:
        kms = get_kms()
        service = IntegrationService(session, kms)
        
        await service.delete(
            workspace=workspace,
            provider=IntegrationProvider.QAIHUB,
            user=current_user,
        )
    except IntegrationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI Hub integration not found",
        )
