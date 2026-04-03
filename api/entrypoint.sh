#!/bin/sh
set -e

cd /srv

echo "[entrypoint] Running database migrations..."
cd /srv/api && python -m alembic upgrade head || echo "[entrypoint] Migration failed or not needed, continuing..."

echo "[entrypoint] Starting API server..."
cd /srv
exec uvicorn api.main:app --host 0.0.0.0 --port 8081 --timeout-graceful-shutdown 30
