"""Initial schema with all tables

Revision ID: 001_initial
Revises: 
Create Date: 2026-01-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE workspacerole AS ENUM ('owner', 'admin', 'viewer')")
    op.execute("CREATE TYPE integrationstatus AS ENUM ('active', 'disabled')")
    op.execute("CREATE TYPE integrationprovider AS ENUM ('qaihub')")
    op.execute("CREATE TYPE artifactkind AS ENUM ('model', 'bundle', 'probe_raw', 'capabilities', 'metric_mapping', 'promptpack', 'other')")
    op.execute("CREATE TYPE runstatus AS ENUM ('queued', 'preparing', 'submitting', 'running', 'collecting', 'evaluating', 'reporting', 'passed', 'failed', 'error')")
    op.execute("CREATE TYPE runtrigger AS ENUM ('manual', 'ci', 'scheduled')")

    # Create workspaces table
    op.create_table(
        'workspaces',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create workspace_memberships table
    op.create_table(
        'workspace_memberships',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', postgresql.ENUM('owner', 'admin', 'viewer', name='workspacerole', create_type=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('workspace_id', 'user_id', name='uq_workspace_user'),
    )
    op.create_index('ix_workspace_memberships_workspace', 'workspace_memberships', ['workspace_id'])
    op.create_index('ix_workspace_memberships_user', 'workspace_memberships', ['user_id'])

    # Create artifacts table (needed by other tables as FK target)
    op.create_table(
        'artifacts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kind', postgresql.ENUM('model', 'bundle', 'probe_raw', 'capabilities', 'metric_mapping', 'promptpack', 'other', name='artifactkind', create_type=False), nullable=False),
        sa.Column('storage_url', sa.String(1000), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('size_bytes', sa.BigInteger, nullable=False),
        sa.Column('original_filename', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_artifacts_workspace', 'artifacts', ['workspace_id'])
    op.create_index('ix_artifacts_sha256', 'artifacts', ['sha256'])

    # Create integrations table
    op.create_table(
        'integrations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', postgresql.ENUM('qaihub', name='integrationprovider', create_type=False), nullable=False),
        sa.Column('status', postgresql.ENUM('active', 'disabled', name='integrationstatus', create_type=False), default='active'),
        sa.Column('token_blob', sa.LargeBinary, nullable=False),
        sa.Column('token_last4', sa.String(4), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('workspace_id', 'provider', name='uq_workspace_provider'),
    )
    op.create_index('ix_integrations_workspace', 'integrations', ['workspace_id'])

    # Create workspace_capabilities table
    op.create_table(
        'workspace_capabilities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('capabilities_artifact_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('artifacts.id'), nullable=False),
        sa.Column('metric_mapping_artifact_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('artifacts.id'), nullable=False),
        sa.Column('probed_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('probe_run_id', postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Create promptpacks table
    op.create_table(
        'promptpacks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=True),
        sa.Column('promptpack_id', sa.String(255), nullable=False),
        sa.Column('version', sa.String(50), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('json_content', postgresql.JSONB, nullable=False),
        sa.Column('published', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('workspace_id', 'promptpack_id', 'version', name='uq_workspace_promptpack_version'),
    )
    op.create_index('ix_promptpacks_workspace', 'promptpacks', ['workspace_id'])
    op.create_index('ix_promptpacks_lookup', 'promptpacks', ['promptpack_id', 'version'])

    # Create pipelines table
    op.create_table(
        'pipelines',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('device_matrix_json', postgresql.JSONB, nullable=False),
        sa.Column('promptpack_ref_json', postgresql.JSONB, nullable=False),
        sa.Column('gates_json', postgresql.JSONB, nullable=False),
        sa.Column('run_policy_json', postgresql.JSONB, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_pipelines_workspace', 'pipelines', ['workspace_id'])

    # Create runs table
    op.create_table(
        'runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('pipeline_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pipelines.id', ondelete='CASCADE'), nullable=False),
        sa.Column('trigger', postgresql.ENUM('manual', 'ci', 'scheduled', name='runtrigger', create_type=False), nullable=False),
        sa.Column('status', postgresql.ENUM('queued', 'preparing', 'submitting', 'running', 'collecting', 'evaluating', 'reporting', 'passed', 'failed', 'error', name='runstatus', create_type=False), default='queued'),
        sa.Column('model_artifact_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('artifacts.id'), nullable=False),
        sa.Column('normalized_metrics_json', postgresql.JSONB, nullable=True),
        sa.Column('gates_eval_json', postgresql.JSONB, nullable=True),
        sa.Column('bundle_artifact_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('artifacts.id'), nullable=True),
        sa.Column('error_code', sa.String(100), nullable=True),
        sa.Column('error_detail', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_runs_workspace', 'runs', ['workspace_id'])
    op.create_index('ix_runs_pipeline', 'runs', ['pipeline_id'])
    op.create_index('ix_runs_status', 'runs', ['status'])

    # Create audit_events table
    op.create_table(
        'audit_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('actor_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('event_json', postgresql.JSONB, nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_audit_events_workspace', 'audit_events', ['workspace_id'])
    op.create_index('ix_audit_events_type', 'audit_events', ['event_type'])
    op.create_index('ix_audit_events_timestamp', 'audit_events', ['timestamp'])

    # Create signing_keys table
    op.create_table(
        'signing_keys',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('public_key', sa.LargeBinary, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Create ci_nonces table
    op.create_table(
        'ci_nonces',
        sa.Column('nonce', sa.String(64), primary_key=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_ci_nonces_expires', 'ci_nonces', ['expires_at'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('ci_nonces')
    op.drop_table('signing_keys')
    op.drop_table('audit_events')
    op.drop_table('runs')
    op.drop_table('pipelines')
    op.drop_table('promptpacks')
    op.drop_table('workspace_capabilities')
    op.drop_table('integrations')
    op.drop_table('artifacts')
    op.drop_table('workspace_memberships')
    op.drop_table('users')
    op.drop_table('workspaces')

    # Drop enum types
    op.execute('DROP TYPE runtrigger')
    op.execute('DROP TYPE runstatus')
    op.execute('DROP TYPE artifactkind')
    op.execute('DROP TYPE integrationprovider')
    op.execute('DROP TYPE integrationstatus')
    op.execute('DROP TYPE workspacerole')
