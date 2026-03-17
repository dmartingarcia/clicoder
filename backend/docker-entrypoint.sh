#!/bin/bash
set -e

echo "Installing dependencies..."
mix deps.get

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

echo "Setting up EventStore..."
mix event_store.create || echo "EventStore already exists"
mix event_store.init || echo "EventStore already initialized"

echo "Starting Phoenix server..."
exec "$@"
