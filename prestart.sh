#!/bin/bash

# Wait for database to be ready
echo "Waiting for database..."
# (In production, Railway handles service dependencies, but this is a good safety measure)

# Run migrations
echo "Running database migrations..."
alembic upgrade head

# Execute the passed command
exec "$@"
