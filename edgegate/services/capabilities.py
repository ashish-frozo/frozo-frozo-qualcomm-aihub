"""
Capabilities service.

Manages workspace capabilities discovered by ProbeSuite:
- Running probe discovery
- Storing capabilities artifacts
- Retrieving capabilities
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edgegate.aihub import (
    MockAIHubClient,
    QAIHubClient,
    ProbeSuite,
    WorkspaceCapabilities,
    MetricMapping,
)
from edgegate.core import get_settings
from edgegate.core.security import LocalKeyManagementService, compute_sha256
from edgegate.db.models import (
    Workspace,
    WorkspaceCapability,
    Artifact,
    ArtifactKind,
    User,
    AuditEvent,
)
from edgegate.services.integration import IntegrationService, IntegrationNotFoundError


# ============================================================================
# Exceptions
# ============================================================================


class CapabilityError(Exception):
    """Base exception for capability operations."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class NoIntegrationError(CapabilityError):
    """Raised when workspace has no AI Hub integration."""

    def __init__(self):
        super().__init__("Workspace does not have an AI Hub integration configured")


class ProbeFailedError(CapabilityError):
    """Raised when probe discovery fails."""

    def __init__(self, message: str):
        super().__init__(f"Probe discovery failed: {message}")


class CapabilityNotFoundError(CapabilityError):
    """Raised when capabilities are not found."""

    def __init__(self, workspace_id: UUID):
        super().__init__(f"No capabilities found for workspace {workspace_id}")


# ============================================================================
# Response Types
# ============================================================================


class CapabilityInfo:
    """Response with capability summary."""

    def __init__(
        self,
        workspace_id: UUID,
        probe_run_id: str,
        probed_at: datetime,
        token_valid: bool,
        device_count: int,
        packaging_types_supported: list,
    ):
        self.workspace_id = workspace_id
        self.probe_run_id = probe_run_id
        self.probed_at = probed_at
        self.token_valid = token_valid
        self.device_count = device_count
        self.packaging_types_supported = packaging_types_supported


# ============================================================================
# Capabilities Service
# ============================================================================


class CapabilitiesService:
    """
    Service for managing workspace capabilities.
    
    Provides:
    - Probe discovery through ProbeSuite
    - Artifact storage for capabilities and metric mappings
    - Capability retrieval
    """

    def __init__(
        self,
        session: AsyncSession,
        kms: LocalKeyManagementService,
    ):
        self.session = session
        self.kms = kms
        self.settings = get_settings()

    async def run_probe(
        self,
        workspace: Workspace,
        user: User,
        use_mock: bool = False,
    ) -> CapabilityInfo:
        """
        Run ProbeSuite to discover capabilities.
        
        Args:
            workspace: The workspace to probe.
            user: User initiating the probe.
            use_mock: Use mock client (for testing).
            
        Returns:
            CapabilityInfo with discovery results.
            
        Raises:
            NoIntegrationError: If no AI Hub integration exists.
            ProbeFailedError: If probe discovery fails.
        """
        # Get AI Hub token
        if use_mock:
            client = MockAIHubClient()
        else:
            integration_service = IntegrationService(self.session, self.kms)
            try:
                from edgegate.db.models import IntegrationProvider
                token = await integration_service.get_token(
                    workspace, IntegrationProvider.QAIHUB
                )
                client = QAIHubClient(token)
            except IntegrationNotFoundError:
                raise NoIntegrationError()

        # Run ProbeSuite
        probe_suite = ProbeSuite(
            client=client,
            workspace_id=workspace.id,
            probe_models_path=Path("edgegate/probe_models"),
        )

        try:
            capabilities = await probe_suite.run_all()
            metric_mapping = await probe_suite.generate_metric_mapping(capabilities)
        except Exception as e:
            raise ProbeFailedError(str(e))

        # Store capabilities artifact
        capabilities_json = capabilities.to_json()
        capabilities_artifact = Artifact(
            workspace_id=workspace.id,
            kind=ArtifactKind.CAPABILITIES,
            storage_url=f"memory://{capabilities.probe_run_id}/capabilities.json",
            sha256=capabilities.sha256(),
            size_bytes=len(capabilities_json),
            original_filename="workspace_capabilities.json",
        )
        self.session.add(capabilities_artifact)
        await self.session.flush()

        # Store metric mapping artifact
        mapping_json = metric_mapping.to_json()
        mapping_artifact = Artifact(
            workspace_id=workspace.id,
            kind=ArtifactKind.METRIC_MAPPING,
            storage_url=f"memory://{capabilities.probe_run_id}/metric_mapping.json",
            sha256=metric_mapping.sha256(),
            size_bytes=len(mapping_json),
            original_filename="metric_mapping.json",
        )
        self.session.add(mapping_artifact)
        await self.session.flush()

        # Store or update workspace capability record
        existing = await self._get_workspace_capability(workspace.id)
        if existing:
            existing.capabilities_artifact_id = capabilities_artifact.id
            existing.metric_mapping_artifact_id = mapping_artifact.id
            existing.probed_at = datetime.now(timezone.utc)
            existing.probe_run_id = UUID(capabilities.probe_run_id)
        else:
            workspace_cap = WorkspaceCapability(
                workspace_id=workspace.id,
                capabilities_artifact_id=capabilities_artifact.id,
                metric_mapping_artifact_id=mapping_artifact.id,
                probe_run_id=UUID(capabilities.probe_run_id),
            )
            self.session.add(workspace_cap)

        # Create audit event
        await self._audit_event(
            workspace_id=workspace.id,
            user_id=user.id,
            event_type="capabilities.probed",
            event_json={
                "probe_run_id": capabilities.probe_run_id,
                "token_valid": capabilities.token_valid,
                "device_count": len(capabilities.devices),
            },
        )

        await self.session.flush()

        # Collect supported packaging types
        packaging_types = set()
        for device in capabilities.devices:
            for pt in device.packaging_types:
                if pt.supported:
                    packaging_types.add(pt.packaging_type)

        return CapabilityInfo(
            workspace_id=workspace.id,
            probe_run_id=capabilities.probe_run_id,
            probed_at=datetime.fromisoformat(capabilities.probed_at.replace("Z", "+00:00")),
            token_valid=capabilities.token_valid,
            device_count=len(capabilities.devices),
            packaging_types_supported=list(packaging_types),
        )

    async def get_capabilities(
        self,
        workspace: Workspace,
    ) -> dict:
        """
        Get current capabilities for a workspace.
        
        Args:
            workspace: The workspace.
            
        Returns:
            Capabilities dictionary.
            
        Raises:
            CapabilityNotFoundError: If no capabilities exist.
        """
        workspace_cap = await self._get_workspace_capability(workspace.id)
        if not workspace_cap:
            raise CapabilityNotFoundError(workspace.id)

        # TODO: In production, retrieve from S3
        # For now, return a summary
        return {
            "workspace_id": str(workspace.id),
            "probe_run_id": str(workspace_cap.probe_run_id),
            "probed_at": workspace_cap.probed_at.isoformat(),
            "capabilities_artifact_id": str(workspace_cap.capabilities_artifact_id),
            "metric_mapping_artifact_id": str(workspace_cap.metric_mapping_artifact_id),
        }

    async def get_metric_mapping(
        self,
        workspace: Workspace,
    ) -> dict:
        """
        Get metric mapping for a workspace.
        
        Args:
            workspace: The workspace.
            
        Returns:
            Metric mapping dictionary.
            
        Raises:
            CapabilityNotFoundError: If no capabilities exist.
        """
        workspace_cap = await self._get_workspace_capability(workspace.id)
        if not workspace_cap:
            raise CapabilityNotFoundError(workspace.id)

        # TODO: In production, retrieve from S3
        # For now, return a summary
        return {
            "workspace_id": str(workspace.id),
            "metric_mapping_artifact_id": str(workspace_cap.metric_mapping_artifact_id),
        }

    # ========================================================================
    # Helper Methods
    # ========================================================================

    async def _get_workspace_capability(
        self,
        workspace_id: UUID,
    ) -> Optional[WorkspaceCapability]:
        """Get workspace capability record."""
        result = await self.session.execute(
            select(WorkspaceCapability).where(
                WorkspaceCapability.workspace_id == workspace_id
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
