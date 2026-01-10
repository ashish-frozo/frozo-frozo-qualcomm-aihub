"""
SQLAlchemy ORM models for EdgeGate.

Implements the data model from PRD §19.
"""

import enum
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID as PyUUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from edgegate.db.session import Base


# ============================================================================
# Enums
# ============================================================================


class WorkspaceRole(str, enum.Enum):
    """Roles for workspace membership."""

    OWNER = "owner"
    ADMIN = "admin"
    VIEWER = "viewer"


class IntegrationStatus(str, enum.Enum):
    """Status of an integration."""

    ACTIVE = "active"
    DISABLED = "disabled"


class IntegrationProvider(str, enum.Enum):
    """Supported integration providers."""

    QAIHUB = "qaihub"


class ArtifactKind(str, enum.Enum):
    """Types of artifacts."""

    MODEL = "model"
    BUNDLE = "bundle"
    PROBE_RAW = "probe_raw"
    CAPABILITIES = "capabilities"
    METRIC_MAPPING = "metric_mapping"
    PROMPTPACK = "promptpack"
    OTHER = "other"


class RunStatus(str, enum.Enum):
    """Run state machine states (PRD §FR5)."""

    QUEUED = "queued"
    PREPARING = "preparing"
    SUBMITTING = "submitting"
    RUNNING = "running"
    COLLECTING = "collecting"
    EVALUATING = "evaluating"
    REPORTING = "reporting"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


class RunTrigger(str, enum.Enum):
    """How a run was triggered."""

    MANUAL = "manual"
    CI = "ci"
    SCHEDULED = "scheduled"


# ============================================================================
# Models
# ============================================================================


class Workspace(Base):
    """Tenant boundary - all resources belong to a workspace."""

    __tablename__ = "workspaces"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # CI secret for HMAC authentication (stored as hash)
    ci_secret_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ci_secret_created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    memberships: Mapped[List["WorkspaceMembership"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    integrations: Mapped[List["Integration"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    pipelines: Mapped[List["Pipeline"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    runs: Mapped[List["Run"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    artifacts: Mapped[List["Artifact"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


class User(Base):
    """User account."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    memberships: Mapped[List["WorkspaceMembership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class WorkspaceMembership(Base):
    """Association between users and workspaces with roles."""

    __tablename__ = "workspace_memberships"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    workspace_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    role: Mapped[WorkspaceRole] = mapped_column(
        Enum(WorkspaceRole, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="memberships")
    user: Mapped["User"] = relationship(back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_user"),
        Index("ix_workspace_memberships_workspace", "workspace_id"),
        Index("ix_workspace_memberships_user", "user_id"),
    )


class Integration(Base):
    """External integration (e.g., AI Hub token)."""

    __tablename__ = "integrations"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    workspace_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    provider: Mapped[IntegrationProvider] = mapped_column(
        Enum(IntegrationProvider, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    status: Mapped[IntegrationStatus] = mapped_column(
        Enum(IntegrationStatus, values_callable=lambda x: [e.value for e in x]),
        default=IntegrationStatus.ACTIVE
    )
    token_blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    token_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="integrations")

    __table_args__ = (
        UniqueConstraint("workspace_id", "provider", name="uq_workspace_provider"),
        Index("ix_integrations_workspace", "workspace_id"),
    )


class WorkspaceCapability(Base):
    """Capabilities discovered by ProbeSuite for a workspace."""

    __tablename__ = "workspace_capabilities"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    workspace_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        unique=True,
    )
    capabilities_artifact_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id"), nullable=False
    )
    metric_mapping_artifact_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id"), nullable=False
    )
    probed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    probe_run_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )


class PromptPack(Base):
    """Versioned collection of prompts for testing."""

    __tablename__ = "promptpacks"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    workspace_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,  # Null for global PromptPacks
    )
    promptpack_id: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    json_content: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "promptpack_id", "version",
            name="uq_workspace_promptpack_version"
        ),
        Index("ix_promptpacks_workspace", "workspace_id"),
        Index("ix_promptpacks_lookup", "promptpack_id", "version"),
    )


class Pipeline(Base):
    """Testing pipeline configuration."""

    __tablename__ = "pipelines"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    workspace_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    device_matrix_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    promptpack_ref_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    gates_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    run_policy_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="pipelines")
    runs: Mapped[List["Run"]] = relationship(back_populates="pipeline")

    __table_args__ = (
        Index("ix_pipelines_workspace", "workspace_id"),
    )


class Run(Base):
    """Execution instance of a pipeline."""

    __tablename__ = "runs"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    workspace_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    pipeline_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="CASCADE")
    )
    trigger: Mapped[RunTrigger] = mapped_column(
        Enum(RunTrigger, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, values_callable=lambda x: [e.value for e in x]),
        default=RunStatus.QUEUED
    )
    model_artifact_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id"), nullable=True
    )
    normalized_metrics_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    gates_eval_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    bundle_artifact_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id"), nullable=True
    )
    error_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="runs")
    pipeline: Mapped["Pipeline"] = relationship(back_populates="runs")

    __table_args__ = (
        Index("ix_runs_workspace", "workspace_id"),
        Index("ix_runs_pipeline", "pipeline_id"),
        Index("ix_runs_status", "status"),
    )


class Artifact(Base):
    """Stored file artifact (models, bundles, probe results)."""

    __tablename__ = "artifacts"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    workspace_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    kind: Mapped[ArtifactKind] = mapped_column(
        Enum(ArtifactKind, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    storage_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    original_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="artifacts")

    __table_args__ = (
        Index("ix_artifacts_workspace", "workspace_id"),
        Index("ix_artifacts_sha256", "sha256"),
    )


class AuditEvent(Base):
    """Audit log entry."""

    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    workspace_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    actor_user_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_audit_events_workspace", "workspace_id"),
        Index("ix_audit_events_type", "event_type"),
        Index("ix_audit_events_timestamp", "timestamp"),
    )


class SigningKey(Base):
    """Ed25519 signing key for evidence bundles."""

    __tablename__ = "signing_keys"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CINonce(Base):
    """Nonce for CI request replay prevention."""

    __tablename__ = "ci_nonces"

    nonce: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        Index("ix_ci_nonces_expires", "expires_at"),
    )
