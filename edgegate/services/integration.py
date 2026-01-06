"""
Integration service.

Manages external integrations (e.g., AI Hub tokens) with:
- Secure token storage using envelope encryption
- Token rotation
- Integration status management
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from edgegate.core.security import (
    KeyManagementService,
    envelope_encrypt,
    envelope_decrypt,
    get_token_last4,
)
from edgegate.db.models import (
    Integration,
    IntegrationProvider,
    IntegrationStatus,
    User,
    Workspace,
    AuditEvent,
)


# ============================================================================
# Exceptions
# ============================================================================


class IntegrationError(Exception):
    """Base exception for integration operations."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class IntegrationNotFoundError(IntegrationError):
    """Raised when integration is not found."""

    def __init__(self, workspace_id: UUID, provider: IntegrationProvider):
        super().__init__(f"No {provider.value} integration found for workspace")
        self.workspace_id = workspace_id
        self.provider = provider


class IntegrationExistsError(IntegrationError):
    """Raised when integration already exists."""

    def __init__(self, workspace_id: UUID, provider: IntegrationProvider):
        super().__init__(f"{provider.value} integration already exists for workspace")
        self.workspace_id = workspace_id
        self.provider = provider


class IntegrationDisabledError(IntegrationError):
    """Raised when integration is disabled."""

    def __init__(self, provider: IntegrationProvider):
        super().__init__(f"{provider.value} integration is disabled")
        self.provider = provider


# ============================================================================
# Response Types
# ============================================================================


class IntegrationInfo:
    """Integration information for API responses."""

    def __init__(
        self,
        id: UUID,
        provider: IntegrationProvider,
        status: IntegrationStatus,
        token_last4: str,
        created_at: datetime,
        updated_at: datetime,
    ):
        self.id = id
        self.provider = provider
        self.status = status
        self.token_last4 = token_last4
        self.created_at = created_at
        self.updated_at = updated_at


# ============================================================================
# Integration Service
# ============================================================================


class IntegrationService:
    """
    Service for managing external integrations.
    
    All tokens are encrypted using envelope encryption before storage.
    """

    def __init__(
        self,
        session: AsyncSession,
        kms: KeyManagementService,
    ):
        self.session = session
        self.kms = kms

    async def connect(
        self,
        workspace: Workspace,
        provider: IntegrationProvider,
        token: str,
        user: User,
    ) -> IntegrationInfo:
        """
        Connect a new integration.
        
        Args:
            workspace: The workspace to connect to.
            provider: The integration provider (e.g., qaihub).
            token: The API token to store (will be encrypted).
            user: The user making the connection.
            
        Returns:
            IntegrationInfo with connection details.
            
        Raises:
            IntegrationExistsError: If integration already exists.
        """
        # Check if integration already exists
        existing = await self._get_integration(workspace.id, provider)
        if existing:
            raise IntegrationExistsError(workspace.id, provider)

        # Encrypt token
        encrypted_token = envelope_encrypt(token.encode(), self.kms)

        # Create integration
        integration = Integration(
            workspace_id=workspace.id,
            provider=provider,
            status=IntegrationStatus.ACTIVE,
            token_blob=encrypted_token,
            token_last4=get_token_last4(token),
            created_by=user.id,
        )
        self.session.add(integration)

        # Create audit event
        await self._audit_event(
            workspace_id=workspace.id,
            user_id=user.id,
            event_type="integration.connected",
            event_json={
                "provider": provider.value,
                "token_last4": get_token_last4(token),
            },
        )

        await self.session.flush()

        return IntegrationInfo(
            id=integration.id,
            provider=integration.provider,
            status=integration.status,
            token_last4=integration.token_last4,
            created_at=integration.created_at,
            updated_at=integration.updated_at,
        )

    async def get_integration(
        self,
        workspace: Workspace,
        provider: IntegrationProvider,
    ) -> IntegrationInfo:
        """
        Get integration info (without decrypted token).
        
        Args:
            workspace: The workspace.
            provider: The integration provider.
            
        Returns:
            IntegrationInfo with integration details.
            
        Raises:
            IntegrationNotFoundError: If integration doesn't exist.
        """
        integration = await self._get_integration(workspace.id, provider)
        if not integration:
            raise IntegrationNotFoundError(workspace.id, provider)

        return IntegrationInfo(
            id=integration.id,
            provider=integration.provider,
            status=integration.status,
            token_last4=integration.token_last4,
            created_at=integration.created_at,
            updated_at=integration.updated_at,
        )

    async def get_token(
        self,
        workspace: Workspace,
        provider: IntegrationProvider,
    ) -> str:
        """
        Get the decrypted token for an integration.
        
        This should only be used by internal services that need
        to make API calls on behalf of the workspace.
        
        Args:
            workspace: The workspace.
            provider: The integration provider.
            
        Returns:
            The decrypted API token.
            
        Raises:
            IntegrationNotFoundError: If integration doesn't exist.
            IntegrationDisabledError: If integration is disabled.
        """
        integration = await self._get_integration(workspace.id, provider)
        if not integration:
            raise IntegrationNotFoundError(workspace.id, provider)

        if integration.status == IntegrationStatus.DISABLED:
            raise IntegrationDisabledError(provider)

        # Decrypt token
        decrypted = envelope_decrypt(integration.token_blob, self.kms)
        return decrypted.decode()

    async def rotate(
        self,
        workspace: Workspace,
        provider: IntegrationProvider,
        new_token: str,
        user: User,
    ) -> IntegrationInfo:
        """
        Rotate the token for an integration.
        
        Args:
            workspace: The workspace.
            provider: The integration provider.
            new_token: The new API token.
            user: The user making the rotation.
            
        Returns:
            IntegrationInfo with updated details.
            
        Raises:
            IntegrationNotFoundError: If integration doesn't exist.
        """
        integration = await self._get_integration(workspace.id, provider)
        if not integration:
            raise IntegrationNotFoundError(workspace.id, provider)

        old_last4 = integration.token_last4

        # Encrypt new token
        encrypted_token = envelope_encrypt(new_token.encode(), self.kms)

        # Update integration
        integration.token_blob = encrypted_token
        integration.token_last4 = get_token_last4(new_token)
        integration.status = IntegrationStatus.ACTIVE  # Re-enable if disabled

        # Create audit event
        await self._audit_event(
            workspace_id=workspace.id,
            user_id=user.id,
            event_type="integration.rotated",
            event_json={
                "provider": provider.value,
                "old_token_last4": old_last4,
                "new_token_last4": get_token_last4(new_token),
            },
        )

        await self.session.flush()

        return IntegrationInfo(
            id=integration.id,
            provider=integration.provider,
            status=integration.status,
            token_last4=integration.token_last4,
            created_at=integration.created_at,
            updated_at=integration.updated_at,
        )

    async def disable(
        self,
        workspace: Workspace,
        provider: IntegrationProvider,
        user: User,
    ) -> IntegrationInfo:
        """
        Disable an integration.
        
        Args:
            workspace: The workspace.
            provider: The integration provider.
            user: The user disabling the integration.
            
        Returns:
            IntegrationInfo with updated status.
            
        Raises:
            IntegrationNotFoundError: If integration doesn't exist.
        """
        integration = await self._get_integration(workspace.id, provider)
        if not integration:
            raise IntegrationNotFoundError(workspace.id, provider)

        # Update status
        integration.status = IntegrationStatus.DISABLED

        # Create audit event
        await self._audit_event(
            workspace_id=workspace.id,
            user_id=user.id,
            event_type="integration.disabled",
            event_json={
                "provider": provider.value,
                "token_last4": integration.token_last4,
            },
        )

        await self.session.flush()

        return IntegrationInfo(
            id=integration.id,
            provider=integration.provider,
            status=integration.status,
            token_last4=integration.token_last4,
            created_at=integration.created_at,
            updated_at=integration.updated_at,
        )

    async def enable(
        self,
        workspace: Workspace,
        provider: IntegrationProvider,
        user: User,
    ) -> IntegrationInfo:
        """
        Re-enable a disabled integration.
        
        Args:
            workspace: The workspace.
            provider: The integration provider.
            user: The user enabling the integration.
            
        Returns:
            IntegrationInfo with updated status.
            
        Raises:
            IntegrationNotFoundError: If integration doesn't exist.
        """
        integration = await self._get_integration(workspace.id, provider)
        if not integration:
            raise IntegrationNotFoundError(workspace.id, provider)

        # Update status
        integration.status = IntegrationStatus.ACTIVE

        # Create audit event
        await self._audit_event(
            workspace_id=workspace.id,
            user_id=user.id,
            event_type="integration.enabled",
            event_json={
                "provider": provider.value,
                "token_last4": integration.token_last4,
            },
        )

        await self.session.flush()

        return IntegrationInfo(
            id=integration.id,
            provider=integration.provider,
            status=integration.status,
            token_last4=integration.token_last4,
            created_at=integration.created_at,
            updated_at=integration.updated_at,
        )

    async def delete(
        self,
        workspace: Workspace,
        provider: IntegrationProvider,
        user: User,
    ) -> None:
        """
        Delete an integration completely.
        
        Args:
            workspace: The workspace.
            provider: The integration provider.
            user: The user deleting the integration.
            
        Raises:
            IntegrationNotFoundError: If integration doesn't exist.
        """
        integration = await self._get_integration(workspace.id, provider)
        if not integration:
            raise IntegrationNotFoundError(workspace.id, provider)

        token_last4 = integration.token_last4

        # Delete integration
        await self.session.delete(integration)

        # Create audit event
        await self._audit_event(
            workspace_id=workspace.id,
            user_id=user.id,
            event_type="integration.deleted",
            event_json={
                "provider": provider.value,
                "token_last4": token_last4,
            },
        )

        await self.session.flush()

    # ========================================================================
    # Helper Methods
    # ========================================================================

    async def _get_integration(
        self,
        workspace_id: UUID,
        provider: IntegrationProvider,
    ) -> Optional[Integration]:
        """Get an integration by workspace and provider."""
        result = await self.session.execute(
            select(Integration).where(
                and_(
                    Integration.workspace_id == workspace_id,
                    Integration.provider == provider,
                )
            )
        )
        return result.scalar_one_or_none()

    async def _audit_event(
        self,
        workspace_id: UUID,
        user_id: UUID,
        event_type: str,
        event_json: dict,
    ) -> None:
        """Create an audit event."""
        event = AuditEvent(
            workspace_id=workspace_id,
            actor_user_id=user_id,
            event_type=event_type,
            event_json=event_json,
        )
        self.session.add(event)
