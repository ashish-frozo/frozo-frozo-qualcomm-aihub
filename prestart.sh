#!/bin/bash
set -e  # Exit on error

# Show environment for debugging (hide secrets)
echo "=== EdgeGate Prestart ==="
echo "APP_ENV: $APP_ENV"
echo "DATABASE_URL_SYNC is set: $([ -n "$DATABASE_URL_SYNC" ] && echo 'yes' || echo 'NO!')"

# Run migrations
echo "Running database migrations..."
alembic upgrade head
echo "Migrations complete!"

# Execute the passed command
exec "$@"
