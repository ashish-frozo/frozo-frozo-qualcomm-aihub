"""
Pipeline service.

Manages testing pipelines with:
- Device matrix configuration
- PromptPack references
- Gates configuration
- Run policy validation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from edgegate.core import get_settings
from edgegate.core.limits import LimitsEnforcer, LimitExceededError
from edgegate.db.models import (
    Pipeline,
    PromptPack,
    Workspace,
    User,
    AuditEvent,
)


# ============================================================================
# Exceptions
# ============================================================================


class PipelineError(Exception):
    """Base exception for Pipeline operations."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class PipelineNotFoundError(PipelineError):
    """Raised when Pipeline is not found."""

    def __init__(self, pipeline_id: UUID):
        super().__init__(f"Pipeline {pipeline_id} not found")
        self.pipeline_id = pipeline_id


class PipelineValidationError(PipelineError):
    """Raised when Pipeline validation fails."""

    def __init__(self, issues: List[str]):
        super().__init__("Pipeline validation failed: " + "; ".join(issues))
        self.issues = issues


class PromptPackRefError(PipelineError):
    """Raised when PromptPack reference is invalid."""

    def __init__(self, promptpack_id: str, version: str):
        super().__init__(f"PromptPack {promptpack_id}@{version} not found or not published")
        self.promptpack_id = promptpack_id
        self.version = version


# ============================================================================
# Configuration Types
# ============================================================================


@dataclass
class DeviceConfig:
    """Configuration for a device in the matrix."""
    name: str
    enabled: bool = True


@dataclass
class PromptPackRef:
    """Reference to a PromptPack."""
    promptpack_id: str
    version: str


@dataclass
class Gate:
    """Gate configuration for pass/fail criteria."""
    metric: str  # e.g., "inference_time_ms"
    operator: str  # "lt", "lte", "gt", "gte", "eq"
    threshold: float
    description: Optional[str] = None


@dataclass
class RunPolicy:
    """Run policy configuration."""
    warmup_runs: int = 1
    measurement_repeats: int = 3
    max_new_tokens: int = 128
    timeout_minutes: int = 20


@dataclass
class PipelineConfig:
    """Full pipeline configuration."""
    name: str
    device_matrix: List[DeviceConfig]
    promptpack_ref: PromptPackRef
    gates: List[Gate]
    run_policy: RunPolicy


# ============================================================================
# Response Types
# ============================================================================


@dataclass
class PipelineInfo:
    """Pipeline information for API responses."""
    id: UUID
    name: str
    device_count: int
    gate_count: int
    promptpack_id: str
    promptpack_version: str
    created_at: datetime
    updated_at: datetime


@dataclass 
class PipelineDetail:
    """Full Pipeline details."""
    id: UUID
    name: str
    device_matrix: List[Dict[str, Any]]
    promptpack_ref: Dict[str, str]
    gates: List[Dict[str, Any]]
    run_policy: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Validation
# ============================================================================


VALID_OPERATORS = {"lt", "lte", "gt", "gte", "eq"}
VALID_METRICS = {
    "inference_time_ms",
    "peak_memory_mb",
    "npu_compute_percent",
    "gpu_compute_percent",
    "cpu_compute_percent",
    "ttft_ms",
    "tps",
}


def validate_pipeline_config(
    device_matrix: List[Dict[str, Any]],
    gates: List[Dict[str, Any]],
    run_policy: Dict[str, Any],
) -> List[str]:
    """
    Validate pipeline configuration.
    
    Returns:
        List of validation error messages (empty if valid).
    """
    settings = get_settings()
    enforcer = LimitsEnforcer(settings)
    issues = []

    # Validate device matrix
    enabled_devices = [d for d in device_matrix if d.get("enabled", True)]
    if len(enabled_devices) == 0:
        issues.append("At least one device must be enabled")
    if len(enabled_devices) > settings.limit_devices_per_run:
        issues.append(f"Maximum {settings.limit_devices_per_run} devices per run")

    # Validate gates
    for i, gate in enumerate(gates):
        if "metric" not in gate:
            issues.append(f"Gate {i}: missing 'metric' field")
        elif gate["metric"] not in VALID_METRICS:
            issues.append(f"Gate {i}: unknown metric '{gate['metric']}'")
        
        if "operator" not in gate:
            issues.append(f"Gate {i}: missing 'operator' field")
        elif gate["operator"] not in VALID_OPERATORS:
            issues.append(f"Gate {i}: invalid operator '{gate['operator']}'")
        
        if "threshold" not in gate:
            issues.append(f"Gate {i}: missing 'threshold' field")
        elif not isinstance(gate["threshold"], (int, float)):
            issues.append(f"Gate {i}: threshold must be a number")

    # Validate run policy
    warmup = run_policy.get("warmup_runs", settings.limit_warmup_runs)
    if warmup != settings.limit_warmup_runs:
        issues.append(f"warmup_runs must be {settings.limit_warmup_runs}")

    repeats = run_policy.get("measurement_repeats", settings.limit_repeats_default)
    if repeats < 1 or repeats > settings.limit_repeats_max:
        issues.append(f"measurement_repeats must be 1-{settings.limit_repeats_max}")

    max_tokens = run_policy.get("max_new_tokens", settings.limit_max_new_tokens_default)
    if max_tokens < 1 or max_tokens > settings.limit_max_new_tokens_max:
        issues.append(f"max_new_tokens must be 1-{settings.limit_max_new_tokens_max}")

    timeout = run_policy.get("timeout_minutes", settings.limit_run_timeout_default_minutes)
    if timeout < 1 or timeout > settings.limit_run_timeout_max_minutes:
        issues.append(f"timeout_minutes must be 1-{settings.limit_run_timeout_max_minutes}")

    return issues


# ============================================================================
# Pipeline Service
# ============================================================================


class PipelineService:
    """
    Service for managing Pipelines.
    
    Pipelines define:
    - Which devices to test on
    - Which PromptPack to use
    - What gates to apply
    - Run policy (warmup, repeats, timeout)
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()

    async def create(
        self,
        workspace: Workspace,
        name: str,
        device_matrix: List[Dict[str, Any]],
        promptpack_ref: Dict[str, str],
        gates: List[Dict[str, Any]],
        run_policy: Dict[str, Any],
        user: User,
    ) -> PipelineInfo:
        """
        Create a new Pipeline.
        
        Args:
            workspace: The workspace.
            name: Pipeline name.
            device_matrix: List of device configurations.
            promptpack_ref: Reference to PromptPack (id + version).
            gates: List of gate configurations.
            run_policy: Run policy configuration.
            user: User creating the pipeline.
            
        Returns:
            PipelineInfo with created details.
            
        Raises:
            PipelineValidationError: If configuration is invalid.
            PromptPackRefError: If PromptPack doesn't exist.
        """
        # Validate configuration
        issues = validate_pipeline_config(device_matrix, gates, run_policy)
        if issues:
            raise PipelineValidationError(issues)

        # Validate PromptPack reference
        pp_id = promptpack_ref.get("promptpack_id", "")
        pp_version = promptpack_ref.get("version", "")
        promptpack = await self._get_promptpack(workspace.id, pp_id, pp_version)
        if not promptpack or not promptpack.published:
            raise PromptPackRefError(pp_id, pp_version)

        # Create pipeline
        pipeline = Pipeline(
            workspace_id=workspace.id,
            name=name,
            device_matrix_json=device_matrix,
            promptpack_ref_json=promptpack_ref,
            gates_json=gates,
            run_policy_json=run_policy,
        )
        self.session.add(pipeline)

        # Audit event
        await self._audit_event(
            workspace_id=workspace.id,
            user_id=user.id,
            event_type="pipeline.created",
            event_json={
                "name": name,
                "promptpack_id": pp_id,
                "promptpack_version": pp_version,
                "device_count": len([d for d in device_matrix if d.get("enabled", True)]),
                "gate_count": len(gates),
            },
        )

        await self.session.flush()

        return PipelineInfo(
            id=pipeline.id,
            name=name,
            device_count=len([d for d in device_matrix if d.get("enabled", True)]),
            gate_count=len(gates),
            promptpack_id=pp_id,
            promptpack_version=pp_version,
            created_at=pipeline.created_at,
            updated_at=pipeline.updated_at,
        )

    async def get(
        self,
        workspace: Workspace,
        pipeline_id: UUID,
    ) -> PipelineDetail:
        """
        Get Pipeline details.
        
        Args:
            workspace: The workspace.
            pipeline_id: Pipeline UUID.
            
        Returns:
            PipelineDetail with full configuration.
            
        Raises:
            PipelineNotFoundError: If not found.
        """
        pipeline = await self._get_pipeline(workspace.id, pipeline_id)
        if not pipeline:
            raise PipelineNotFoundError(pipeline_id)

        return PipelineDetail(
            id=pipeline.id,
            name=pipeline.name,
            device_matrix=pipeline.device_matrix_json,
            promptpack_ref=pipeline.promptpack_ref_json,
            gates=pipeline.gates_json,
            run_policy=pipeline.run_policy_json,
            created_at=pipeline.created_at,
            updated_at=pipeline.updated_at,
        )

    async def list_all(
        self,
        workspace: Workspace,
    ) -> List[PipelineInfo]:
        """
        List all Pipelines in a workspace.
        
        Args:
            workspace: The workspace.
            
        Returns:
            List of PipelineInfo.
        """
        result = await self.session.execute(
            select(Pipeline)
            .where(Pipeline.workspace_id == workspace.id)
            .order_by(Pipeline.created_at.desc())
        )
        pipelines = result.scalars().all()

        return [
            PipelineInfo(
                id=p.id,
                name=p.name,
                device_count=len([d for d in p.device_matrix_json if d.get("enabled", True)]),
                gate_count=len(p.gates_json),
                promptpack_id=p.promptpack_ref_json.get("promptpack_id", ""),
                promptpack_version=p.promptpack_ref_json.get("version", ""),
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in pipelines
        ]

    async def update(
        self,
        workspace: Workspace,
        pipeline_id: UUID,
        name: Optional[str] = None,
        device_matrix: Optional[List[Dict[str, Any]]] = None,
        promptpack_ref: Optional[Dict[str, str]] = None,
        gates: Optional[List[Dict[str, Any]]] = None,
        run_policy: Optional[Dict[str, Any]] = None,
        user: Optional[User] = None,
    ) -> PipelineInfo:
        """
        Update a Pipeline.
        
        Args:
            workspace: The workspace.
            pipeline_id: Pipeline UUID.
            name: New name (optional).
            device_matrix: New device matrix (optional).
            promptpack_ref: New PromptPack reference (optional).
            gates: New gates (optional).
            run_policy: New run policy (optional).
            user: User updating.
            
        Returns:
            Updated PipelineInfo.
            
        Raises:
            PipelineNotFoundError: If not found.
            PipelineValidationError: If new configuration is invalid.
        """
        pipeline = await self._get_pipeline(workspace.id, pipeline_id)
        if not pipeline:
            raise PipelineNotFoundError(pipeline_id)

        # Apply updates
        if name is not None:
            pipeline.name = name
        if device_matrix is not None:
            pipeline.device_matrix_json = device_matrix
        if promptpack_ref is not None:
            # Validate PromptPack reference
            pp_id = promptpack_ref.get("promptpack_id", "")
            pp_version = promptpack_ref.get("version", "")
            promptpack = await self._get_promptpack(workspace.id, pp_id, pp_version)
            if not promptpack or not promptpack.published:
                raise PromptPackRefError(pp_id, pp_version)
            pipeline.promptpack_ref_json = promptpack_ref
        if gates is not None:
            pipeline.gates_json = gates
        if run_policy is not None:
            pipeline.run_policy_json = run_policy

        # Validate final configuration
        issues = validate_pipeline_config(
            pipeline.device_matrix_json,
            pipeline.gates_json,
            pipeline.run_policy_json,
        )
        if issues:
            raise PipelineValidationError(issues)

        # Audit event
        if user:
            await self._audit_event(
                workspace_id=workspace.id,
                user_id=user.id,
                event_type="pipeline.updated",
                event_json={"pipeline_id": str(pipeline_id)},
            )

        await self.session.flush()

        pp_ref = pipeline.promptpack_ref_json
        return PipelineInfo(
            id=pipeline.id,
            name=pipeline.name,
            device_count=len([d for d in pipeline.device_matrix_json if d.get("enabled", True)]),
            gate_count=len(pipeline.gates_json),
            promptpack_id=pp_ref.get("promptpack_id", ""),
            promptpack_version=pp_ref.get("version", ""),
            created_at=pipeline.created_at,
            updated_at=pipeline.updated_at,
        )

    async def delete(
        self,
        workspace: Workspace,
        pipeline_id: UUID,
        user: User,
    ) -> None:
        """
        Delete a Pipeline.
        
        Args:
            workspace: The workspace.
            pipeline_id: Pipeline UUID.
            user: User deleting.
            
        Raises:
            PipelineNotFoundError: If not found.
        """
        pipeline = await self._get_pipeline(workspace.id, pipeline_id)
        if not pipeline:
            raise PipelineNotFoundError(pipeline_id)

        await self.session.delete(pipeline)

        # Audit event
        await self._audit_event(
            workspace_id=workspace.id,
            user_id=user.id,
            event_type="pipeline.deleted",
            event_json={"pipeline_id": str(pipeline_id), "name": pipeline.name},
        )

        await self.session.flush()

    # ========================================================================
    # Helper Methods
    # ========================================================================

    async def _get_pipeline(
        self,
        workspace_id: UUID,
        pipeline_id: UUID,
    ) -> Optional[Pipeline]:
        """Get a Pipeline by workspace and ID."""
        result = await self.session.execute(
            select(Pipeline).where(
                and_(
                    Pipeline.workspace_id == workspace_id,
                    Pipeline.id == pipeline_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def _get_promptpack(
        self,
        workspace_id: UUID,
        promptpack_id: str,
        version: str,
    ) -> Optional[PromptPack]:
        """Get a PromptPack by workspace, id, and version."""
        result = await self.session.execute(
            select(PromptPack).where(
                and_(
                    PromptPack.workspace_id == workspace_id,
                    PromptPack.promptpack_id == promptpack_id,
                    PromptPack.version == version,
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
