#!/bin/bash
set -e

echo "Waiting for database at ${DB_HOST:-db}:${DB_PORT:-5432}..."
until pg_isready -h "${DB_HOST:-db}" -p "${DB_PORT:-5432}" -U "${POSTGRES_USER:-postgres}" -q; do
  sleep 1
done
echo "Database is ready."

echo "Running migrations..."
mix ecto.create --quiet
mix ecto.migrate --quiet

exec mix phx.server
