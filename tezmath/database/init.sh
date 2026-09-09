#!/bin/bash
# Run all migrations in order
set -e

DB_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/tezmath}"

echo "Running migrations..."
for f in /migrations/*.sql; do
    echo "Applying $f..."
    psql "$DB_URL" -f "$f"
done
echo "Migrations complete."
