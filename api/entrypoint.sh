#!/bin/sh
set -e

echo "[entrypoint] Running database migrations..."
python -m alembic upgrade head || echo "[entrypoint] Migration failed or not needed, continuing..."

echo "[entrypoint] Starting API server..."
exec uvicorn main:app --host 0.0.0.0 --port 8081 --timeout-graceful-shutdown 30
