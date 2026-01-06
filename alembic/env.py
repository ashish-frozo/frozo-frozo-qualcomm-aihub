"""
Alembic environment configuration.

Supports both sync and async database operations.
"""

import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy import create_engine

from alembic import context

# Import all models to ensure they're registered with Base.metadata
from edgegate.db.models import (
    Workspace,
    User,
    WorkspaceMembership,
    Integration,
    WorkspaceCapability,
    PromptPack,
    Pipeline,
    Run,
    Artifact,
    AuditEvent,
    SigningKey,
    CINonce,
)
from edgegate.db.session import Base

from edgegate.core import get_settings

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata from our models
target_metadata = Base.metadata

# Get database URL from environment or config
def get_url():
    """Get database URL from environment or alembic.ini."""
    settings = get_settings()
    return settings.database_url_sync


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.
    Calls to context.execute() emit the given string to the script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate
    a connection with the context.
    """
    connectable = create_engine(
        get_url(),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
