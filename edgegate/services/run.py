"""
Run service and state machine.

Manages test runs with:
- State machine (PRD §FR5)
- Run lifecycle management
- Gate evaluation
- Evidence bundle creation
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from edgegate.core import get_settings
from edgegate.db.models import (
    Run,
    RunStatus,
    RunTrigger,
    Pipeline,
    PromptPack,
    Artifact,
    ArtifactKind,
    Workspace,
    User,
    AuditEvent,
)


# ============================================================================
# Exceptions
# ============================================================================


class RunError(Exception):
    """Base exception for Run operations."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class RunNotFoundError(RunError):
    """Raised when Run is not found."""

    def __init__(self, run_id: UUID):
        super().__init__(f"Run {run_id} not found")
        self.run_id = run_id


class InvalidStateTransitionError(RunError):
    """Raised when state transition is invalid."""

    def __init__(self, current: RunStatus, target: RunStatus):
        super().__init__(f"Cannot transition from {current.value} to {target.value}")
        self.current = current
        self.target = target


class PipelineNotFoundError(RunError):
    """Raised when Pipeline is not found."""

    def __init__(self, pipeline_id: UUID):
        super().__init__(f"Pipeline {pipeline_id} not found")
        self.pipeline_id = pipeline_id


class ArtifactNotFoundError(RunError):
    """Raised when Artifact is not found."""

    def __init__(self, artifact_id: UUID):
        super().__init__(f"Artifact {artifact_id} not found")
        self.artifact_id = artifact_id


# ============================================================================
# State Machine
# ============================================================================


# Valid state transitions per PRD §FR5
STATE_TRANSITIONS: Dict[RunStatus, List[RunStatus]] = {
    RunStatus.QUEUED: [RunStatus.PREPARING, RunStatus.ERROR],
    RunStatus.PREPARING: [RunStatus.SUBMITTING, RunStatus.ERROR],
    RunStatus.SUBMITTING: [RunStatus.RUNNING, RunStatus.ERROR],
    RunStatus.RUNNING: [RunStatus.COLLECTING, RunStatus.ERROR],
    RunStatus.COLLECTING: [RunStatus.EVALUATING, RunStatus.ERROR],
    RunStatus.EVALUATING: [RunStatus.REPORTING, RunStatus.ERROR],
    RunStatus.REPORTING: [RunStatus.PASSED, RunStatus.FAILED, RunStatus.ERROR],
    # Terminal states
    RunStatus.PASSED: [],
    RunStatus.FAILED: [],
    RunStatus.ERROR: [],
}


def can_transition(current: RunStatus, target: RunStatus) -> bool:
    """Check if state transition is valid."""
    return target in STATE_TRANSITIONS.get(current, [])


def is_terminal(status: RunStatus) -> bool:
    """Check if status is terminal (no further transitions)."""
    return status in {RunStatus.PASSED, RunStatus.FAILED, RunStatus.ERROR}


# ============================================================================
# Gate Evaluation
# ============================================================================


@dataclass
class GateResult:
    """Result of a single gate evaluation."""
    metric: str
    operator: str
    threshold: float
    actual_value: float
    passed: bool
    description: Optional[str] = None


@dataclass
class GatesEvaluation:
    """Result of all gates evaluation."""
    passed: bool
    gate_results: List[GateResult] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "gates": [asdict(g) for g in self.gate_results],
        }


def evaluate_gate(
    gate: Dict[str, Any],
    metrics: Dict[str, float],
) -> GateResult:
    """
    Evaluate a single gate against metrics.
    
    Args:
        gate: Gate configuration (metric, operator, threshold).
        metrics: Normalized metrics dict.
        
    Returns:
        GateResult with evaluation.
    """
    metric = gate["metric"]
    operator = gate["operator"]
    threshold = gate["threshold"]
    
    actual = metrics.get(metric)
    
    if actual is None:
        # Metric not available - gate fails
        return GateResult(
            metric=metric,
            operator=operator,
            threshold=threshold,
            actual_value=float('nan'),
            passed=False,
            description=f"Metric '{metric}' not available",
        )
    
    # Evaluate based on operator
    passed = False
    if operator == "lt":
        passed = actual < threshold
    elif operator == "lte":
        passed = actual <= threshold
    elif operator == "gt":
        passed = actual > threshold
    elif operator == "gte":
        passed = actual >= threshold
    elif operator == "eq":
        passed = abs(actual - threshold) < 1e-9
    
    return GateResult(
        metric=metric,
        operator=operator,
        threshold=threshold,
        actual_value=actual,
        passed=passed,
        description=gate.get("description"),
    )


def evaluate_gates(
    gates: List[Dict[str, Any]],
    metrics: Dict[str, float],
) -> GatesEvaluation:
    """
    Evaluate all gates against metrics.
    
    Args:
        gates: List of gate configurations.
        metrics: Normalized metrics dict.
        
    Returns:
        GatesEvaluation with overall result.
    """
    results = [evaluate_gate(g, metrics) for g in gates]
    all_passed = all(r.passed for r in results)
    
    return GatesEvaluation(
        passed=all_passed,
        gate_results=results,
    )


# ============================================================================
# Metrics Aggregation
# ============================================================================


def aggregate_metrics_median(
    measurements: List[Dict[str, float]],
    warmup_count: int = 1,
) -> Dict[str, float]:
    """
    Aggregate metrics using median-of-N with warmup exclusion.
    
    Args:
        measurements: List of measurement dicts (one per repeat).
        warmup_count: Number of warmup runs to exclude.
        
    Returns:
        Aggregated metrics dict with median values.
    """
    if not measurements:
        return {}
    
    # Exclude warmup runs
    valid_measurements = measurements[warmup_count:]
    if not valid_measurements:
        return {}
    
    # Collect all metric names
    all_metrics = set()
    for m in valid_measurements:
        all_metrics.update(m.keys())
    
    # Calculate median for each metric
    result = {}
    for metric in all_metrics:
        values = [m[metric] for m in valid_measurements if metric in m]
        if values:
            values.sort()
            n = len(values)
            if n % 2 == 0:
                result[metric] = (values[n//2 - 1] + values[n//2]) / 2
            else:
                result[metric] = values[n//2]
    
    return result


def detect_flaky_metrics(
    measurements: List[Dict[str, float]],
    cv_threshold: float = 0.1,  # 10% coefficient of variation
) -> List[str]:
    """
    Detect flaky metrics based on coefficient of variation.
    
    Args:
        measurements: List of measurement dicts.
        cv_threshold: CV threshold above which a metric is considered flaky.
        
    Returns:
        List of flaky metric names.
    """
    import statistics
    
    if len(measurements) < 2:
        return []
    
    all_metrics = set()
    for m in measurements:
        all_metrics.update(m.keys())
    
    flaky = []
    for metric in all_metrics:
        values = [m[metric] for m in measurements if metric in m]
        if len(values) >= 2:
            mean = statistics.mean(values)
            if mean > 0:
                stdev = statistics.stdev(values)
                cv = stdev / mean
                if cv > cv_threshold:
                    flaky.append(metric)
    
    return flaky


# ============================================================================
# Response Types
# ============================================================================


@dataclass
class RunInfo:
    """Run information for API responses."""
    id: UUID
    pipeline_id: UUID
    status: RunStatus
    trigger: RunTrigger
    created_at: datetime
    updated_at: datetime


@dataclass
class RunDetail:
    """Full Run details."""
    id: UUID
    pipeline_id: UUID
    pipeline_name: str
    status: RunStatus
    trigger: RunTrigger
    model_artifact_id: UUID
    normalized_metrics: Optional[Dict[str, Any]]
    gates_eval: Optional[Dict[str, Any]]
    bundle_artifact_id: Optional[UUID]
    error_code: Optional[str]
    error_detail: Optional[str]
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Run Service
# ============================================================================


class RunService:
    """
    Service for managing Runs.
    
    Handles run lifecycle, state transitions, and gate evaluation.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()

    async def create(
        self,
        workspace: Workspace,
        pipeline_id: UUID,
        model_artifact_id: UUID,
        trigger: RunTrigger,
        user: Optional[User] = None,
    ) -> RunInfo:
        """
        Create a new Run.
        
        Args:
            workspace: The workspace.
            pipeline_id: Pipeline to execute.
            model_artifact_id: Model artifact to test.
            trigger: How the run was triggered.
            user: User triggering (optional for CI).
            
        Returns:
            RunInfo with created run details.
            
        Raises:
            PipelineNotFoundError: If pipeline doesn't exist.
            ArtifactNotFoundError: If artifact doesn't exist.
        """
        # Verify pipeline exists
        pipeline = await self._get_pipeline(workspace.id, pipeline_id)
        if not pipeline:
            raise PipelineNotFoundError(pipeline_id)

        # Verify artifact exists
        artifact = await self._get_artifact(workspace.id, model_artifact_id)
        if not artifact:
            raise ArtifactNotFoundError(model_artifact_id)

        # Create run
        run = Run(
            workspace_id=workspace.id,
            pipeline_id=pipeline_id,
            trigger=trigger,
            status=RunStatus.QUEUED,
            model_artifact_id=model_artifact_id,
        )
        self.session.add(run)

        # Audit event
        await self._audit_event(
            workspace_id=workspace.id,
            user_id=user.id if user else None,
            event_type="run.created",
            event_json={
                "pipeline_id": str(pipeline_id),
                "model_artifact_id": str(model_artifact_id),
                "trigger": trigger.value,
            },
        )

        await self.session.flush()

        return RunInfo(
            id=run.id,
            pipeline_id=pipeline_id,
            status=run.status,
            trigger=trigger,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    async def get(
        self,
        workspace: Workspace,
        run_id: UUID,
    ) -> RunDetail:
        """
        Get Run details.
        
        Args:
            workspace: The workspace.
            run_id: Run UUID.
            
        Returns:
            RunDetail with full details.
            
        Raises:
            RunNotFoundError: If not found.
        """
        run = await self._get_run(workspace.id, run_id)
        if not run:
            raise RunNotFoundError(run_id)

        # Get pipeline name
        pipeline = await self._get_pipeline(workspace.id, run.pipeline_id)
        pipeline_name = pipeline.name if pipeline else "Unknown"

        return RunDetail(
            id=run.id,
            pipeline_id=run.pipeline_id,
            pipeline_name=pipeline_name,
            status=run.status,
            trigger=run.trigger,
            model_artifact_id=run.model_artifact_id,
            normalized_metrics=run.normalized_metrics_json,
            gates_eval=run.gates_eval_json,
            bundle_artifact_id=run.bundle_artifact_id,
            error_code=run.error_code,
            error_detail=run.error_detail,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    async def list_all(
        self,
        workspace: Workspace,
        pipeline_id: Optional[UUID] = None,
        limit: int = 50,
    ) -> List[RunInfo]:
        """
        List Runs.
        
        Args:
            workspace: The workspace.
            pipeline_id: Filter by pipeline (optional).
            limit: Maximum results.
            
        Returns:
            List of RunInfo.
        """
        query = select(Run).where(Run.workspace_id == workspace.id)
        
        if pipeline_id:
            query = query.where(Run.pipeline_id == pipeline_id)
        
        query = query.order_by(Run.created_at.desc()).limit(limit)
        
        result = await self.session.execute(query)
        runs = result.scalars().all()

        return [
            RunInfo(
                id=r.id,
                pipeline_id=r.pipeline_id,
                status=r.status,
                trigger=r.trigger,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in runs
        ]

    async def transition(
        self,
        workspace: Workspace,
        run_id: UUID,
        new_status: RunStatus,
        metrics: Optional[Dict[str, Any]] = None,
        gates_eval: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
        error_detail: Optional[str] = None,
        bundle_artifact_id: Optional[UUID] = None,
    ) -> RunInfo:
        """
        Transition Run to a new state.
        
        Args:
            workspace: The workspace.
            run_id: Run UUID.
            new_status: Target status.
            metrics: Normalized metrics (for EVALUATING → REPORTING).
            gates_eval: Gates evaluation (for EVALUATING → REPORTING).
            error_code: Error code (for → ERROR).
            error_detail: Error message (for → ERROR).
            bundle_artifact_id: Bundle artifact (for → PASSED/FAILED).
            
        Returns:
            Updated RunInfo.
            
        Raises:
            RunNotFoundError: If not found.
            InvalidStateTransitionError: If transition is invalid.
        """
        run = await self._get_run(workspace.id, run_id)
        if not run:
            raise RunNotFoundError(run_id)

        if not can_transition(run.status, new_status):
            raise InvalidStateTransitionError(run.status, new_status)

        # Update status and related fields
        run.status = new_status
        
        if metrics is not None:
            run.normalized_metrics_json = metrics
        if gates_eval is not None:
            run.gates_eval_json = gates_eval
        if error_code is not None:
            run.error_code = error_code
        if error_detail is not None:
            run.error_detail = error_detail
        if bundle_artifact_id is not None:
            run.bundle_artifact_id = bundle_artifact_id

        await self.session.flush()

        return RunInfo(
            id=run.id,
            pipeline_id=run.pipeline_id,
            status=run.status,
            trigger=run.trigger,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    async def set_error(
        self,
        workspace: Workspace,
        run_id: UUID,
        error_code: str,
        error_detail: str,
    ) -> RunInfo:
        """
        Transition Run to ERROR state.
        
        Args:
            workspace: The workspace.
            run_id: Run UUID.
            error_code: Error classification code.
            error_detail: Detailed error message.
            
        Returns:
            Updated RunInfo.
        """
        return await self.transition(
            workspace=workspace,
            run_id=run_id,
            new_status=RunStatus.ERROR,
            error_code=error_code,
            error_detail=error_detail,
        )

    # ========================================================================
    # Helper Methods
    # ========================================================================

    async def _get_run(
        self,
        workspace_id: UUID,
        run_id: UUID,
    ) -> Optional[Run]:
        """Get a Run by workspace and ID."""
        result = await self.session.execute(
            select(Run).where(
                and_(
                    Run.workspace_id == workspace_id,
                    Run.id == run_id,
                )
            )
        )
        return result.scalar_one_or_none()

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

    async def _get_artifact(
        self,
        workspace_id: UUID,
        artifact_id: UUID,
    ) -> Optional[Artifact]:
        """Get an Artifact by workspace and ID."""
        result = await self.session.execute(
            select(Artifact).where(
                and_(
                    Artifact.workspace_id == workspace_id,
                    Artifact.id == artifact_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def _audit_event(
        self,
        workspace_id: UUID,
        user_id: Optional[UUID],
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
