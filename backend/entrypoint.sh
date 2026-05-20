#!/bin/bash
set -e

DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${POSTGRES_USER:-postgres}"

printf "Esperando a PostgreSQL"
until psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -c '\q' >/dev/null 2>&1; do
  printf "."
  sleep 2
done
echo " listo."

exec mix phx.server
