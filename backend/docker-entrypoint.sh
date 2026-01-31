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

# Crear base de datos de eventos si no existe
echo "Creating event store database..."
mix event_store.create || echo "Event store database already exists"

# Ejecutar migraciones
echo "Running migrations..."
mix ecto.migrate || echo "Migrations already up to date"

# Inicializar event store
echo "Initializing event store..."
mix event_store.init || echo "Event store already initialized"

echo "Starting Phoenix server..."
exec "$@"
