#!/bin/bash
set -e  # Exit on error

# Show environment for debugging (hide secrets)
echo "=== EdgeGate Prestart ==="
echo "APP_ENV: $APP_ENV"
echo "DATABASE_URL_SYNC is set: $([ -n "$DATABASE_URL_SYNC" ] && echo 'yes' || echo 'NO!')"

# Force migrate option - resets alembic version and re-runs from scratch
if [ "$FORCE_MIGRATE" = "true" ]; then
    echo "FORCE_MIGRATE enabled - resetting alembic version..."
    alembic stamp base || echo "No existing version to reset"
fi

# Run migrations
echo "Running database migrations..."
alembic upgrade head
echo "Migrations complete!"

# Execute the passed command
exec "$@"
