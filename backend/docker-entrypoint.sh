#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
until pg_isready -h db -U postgres; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 1
done

echo "PostgreSQL is up - setting up databases"

# Crear base de datos de aplicación si no existe
echo "Creating application database..."
mix ecto.create || echo "Database already exists"

# Ejecutar migraciones
echo "Running migrations..."
mix ecto.migrate || echo "Migrations already up to date"

echo "Starting Phoenix server..."
exec "$@"
