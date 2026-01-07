#!/bin/bash
set -e  # Exit on error

# Show environment for debugging (hide secrets)
echo "=== EdgeGate Prestart ==="
echo "APP_ENV: $APP_ENV"
echo "DATABASE_URL_SYNC is set: $([ -n "$DATABASE_URL_SYNC" ] && echo 'yes' || echo 'NO!')"

# Force migrate option - directly clears alembic_version table
if [ "$FORCE_MIGRATE" = "true" ]; then
    echo "FORCE_MIGRATE enabled - clearing alembic_version table..."
    # Use psql to directly delete the version marker
    psql "$DATABASE_URL_SYNC" -c "DELETE FROM alembic_version;" 2>/dev/null || echo "No alembic_version table yet (this is fine)"
fi

# Run migrations
echo "Running database migrations..."
alembic upgrade head
echo "Migrations complete!"

# Execute the passed command
exec "$@"
