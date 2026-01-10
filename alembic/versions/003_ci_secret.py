"""add ci_secret to workspaces

Revision ID: 003_ci_secret
Revises: 002_nullable_model_artifact
Create Date: 2026-01-10

Adds CI secret fields to workspaces table for GitHub Actions integration.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '003_ci_secret'
down_revision = '002_nullable_model_artifact'
branch_labels = None
depends_on = None


def upgrade():
    # Add CI secret fields to workspaces
    op.add_column('workspaces', sa.Column('ci_secret_hash', sa.String(length=255), nullable=True))
    op.add_column('workspaces', sa.Column('ci_secret_created_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('workspaces', 'ci_secret_created_at')
    op.drop_column('workspaces', 'ci_secret_hash')
