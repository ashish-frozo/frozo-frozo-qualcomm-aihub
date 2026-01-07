"""make model_artifact_id nullable

Revision ID: 002_nullable_model_artifact
Revises: 001_initial
Create Date: 2026-01-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_nullable_model_artifact'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make model_artifact_id nullable in runs table
    op.alter_column('runs', 'model_artifact_id',
               existing_type=sa.UUID(),
               nullable=True)


def downgrade() -> None:
    # Make model_artifact_id non-nullable in runs table
    op.alter_column('runs', 'model_artifact_id',
               existing_type=sa.UUID(),
               nullable=False)
