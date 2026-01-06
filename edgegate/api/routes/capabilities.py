"""
Capabilities API routes.

Provides:
- POST /workspaces/{workspace_id}/capabilities/probe - Run capability discovery
- GET /workspaces/{workspace_id}/capabilities - Get current capabilities
- GET /workspaces/{workspace_id}/capabilities/metrics - Get metric mapping
"""

from __future__ import annotations

from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from edgegate.db import get_session
from edgegate.core import get_settings
from edgegate.core.security import LocalKeyManagementService
from edgegate.services.capabilities import (
    CapabilitiesService,
    NoIntegrationError,
    ProbeFailedError,
    CapabilityNotFoundError,
)
from edgegate.api.deps import CurrentUser, WorkspaceAdmin


router = APIRouter(tags=["Capabilities"])


# ============================================================================
# Schemas
# ============================================================================


class ProbeResponse(BaseModel):
    """Response after running probe discovery."""

    workspace_id: UUID
    probe_run_id: str
    probed_at: datetime
    token_valid: bool
    device_count: int
    packaging_types_supported: List[str]


class CapabilitiesResponse(BaseModel):
    """Response with capabilities summary."""

    workspace_id: str
    probe_run_id: str
    probed_at: str
    capabilities_artifact_id: str
    metric_mapping_artifact_id: str


class MetricMappingResponse(BaseModel):
    """Response with metric mapping reference."""

    workspace_id: str
    metric_mapping_artifact_id: str


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
    "/workspaces/{workspace_id}/capabilities/probe",
    response_model=ProbeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run capability discovery probe",
)
async def run_probe(
    workspace: WorkspaceAdmin,
    current_user: CurrentUser,
    use_mock: bool = Query(
        default=False,
        description="Use mock AI Hub client (for testing)",
    ),
    session: AsyncSession = Depends(get_session),
) -> ProbeResponse:
    """
    Run ProbeSuite to discover AI Hub capabilities.
    
    This probes the AI Hub API to discover:
    - Available devices
    - Supported packaging types (torch, onnx, onnx_external, aimet)
    - Profiling capabilities
    - Inference capabilities
    
    Results are stored as workspace_capabilities.json and metric_mapping.json.
    
    Requires at least admin role.
    """
    try:
        kms = get_kms()
        service = CapabilitiesService(session, kms)
        
        result = await service.run_probe(
            workspace=workspace,
            user=current_user,
            use_mock=use_mock,
        )
        
        return ProbeResponse(
            workspace_id=result.workspace_id,
            probe_run_id=result.probe_run_id,
            probed_at=result.probed_at,
            token_valid=result.token_valid,
            device_count=result.device_count,
            packaging_types_supported=result.packaging_types_supported,
        )
    except NoIntegrationError:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail="AI Hub integration not configured. Connect integration first.",
        )
    except ProbeFailedError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=e.message,
        )


@router.get(
    "/workspaces/{workspace_id}/capabilities",
    response_model=CapabilitiesResponse,
    summary="Get workspace capabilities",
)
async def get_capabilities(
    workspace: WorkspaceAdmin,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> CapabilitiesResponse:
    """
    Get current capabilities for a workspace.
    
    Returns references to the capabilities and metric mapping artifacts.
    Run the probe endpoint first to discover capabilities.
    
    Requires at least admin role.
    """
    try:
        kms = get_kms()
        service = CapabilitiesService(session, kms)
        
        result = await service.get_capabilities(workspace)
        
        return CapabilitiesResponse(**result)
    except CapabilityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No capabilities found. Run probe discovery first.",
        )


@router.get(
    "/workspaces/{workspace_id}/capabilities/metrics",
    response_model=MetricMappingResponse,
    summary="Get metric mapping",
)
async def get_metric_mapping(
    workspace: WorkspaceAdmin,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> MetricMappingResponse:
    """
    Get the metric mapping for the workspace.
    
    Contains JSONPath specifications for extracting metrics
    from AI Hub profile results.
    
    Requires at least admin role.
    """
    try:
        kms = get_kms()
        service = CapabilitiesService(session, kms)
        
        result = await service.get_metric_mapping(workspace)
        
        return MetricMappingResponse(**result)
    except CapabilityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No capabilities found. Run probe discovery first.",
        )
