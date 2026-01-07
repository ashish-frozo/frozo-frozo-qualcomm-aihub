#!/bin/bash
set -e  # Exit on error

# Show environment for debugging (hide secrets)
echo "=== EdgeGate Prestart ==="
echo "APP_ENV: $APP_ENV"
echo "DATABASE_URL_SYNC is set: $([ -n "$DATABASE_URL_SYNC" ] && echo 'yes' || echo 'NO!')"

# Debug: List migration files
echo "Migration files in alembic/versions:"
ls -la alembic/versions/

# Force migrate option - directly clears alembic_version table
if [ "$FORCE_MIGRATE" = "true" ]; then
    echo "FORCE_MIGRATE enabled - clearing alembic_version table..."
    # Use psql to directly delete the version marker
    psql "$DATABASE_URL_SYNC" -c "DELETE FROM alembic_version;" 2>/dev/null || echo "No alembic_version table yet (this is fine)"
fi

# Stamp head option - marks the database as up-to-date without running migrations
if [ "$STAMP_HEAD" = "true" ]; then
    echo "STAMP_HEAD enabled - marking database as up-to-date..."
    alembic stamp head
fi

# Debug: Alembic state
echo "Alembic History:"
alembic history
echo "Alembic Current:"
alembic current || echo "No current version"
echo "Alembic Heads:"
alembic heads

# Run migrations
echo "Running database migrations..."
alembic upgrade head
echo "Migrations complete!"

# Debug: Check if users table exists now
echo "Checking for 'users' table..."
psql "$DATABASE_URL_SYNC" -c "\dt users" || echo "Users table STILL missing!"

# Execute the passed command
exec "$@"
