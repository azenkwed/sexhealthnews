#!/usr/bin/env bash
set -euo pipefail

echo ""
echo " ════════════════════════════════════"
echo " SEX HEALTH NEWS — ADMIN DASHBOARD"
echo " ════════════════════════════════════"
echo ""

# Check for .env file
if [ ! -f .env ]; then
    echo "[!] No .env file found. Copy .env.example to .env and add your API keys."
    exit 1
fi

# Extract PostgreSQL connection info from .env
DB_URL="${DATABASE_URL:-$(grep -E '^DATABASE_URL=' .env 2>/dev/null | cut -d= -f2-)}"
DB_HOST=$(echo "$DB_URL" | sed -E 's|.*@([^:/]+).*|\1|')
DB_PORT=$(echo "$DB_URL" | sed -E 's|.*:([0-9]+)/.*|\1|')
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

# Check if PostgreSQL is ready
echo "[*] Checking PostgreSQL at $DB_HOST:$DB_PORT..."
if ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -q 2>/dev/null; then
    echo "[!] PostgreSQL is not running."
    echo "[*] Attempting to start PostgreSQL with Docker..."

    # Check if start-postgres.sh exists
    if [ ! -f "start-postgres.sh" ]; then
        echo "[!] start-postgres.sh not found in current directory."
        exit 1
    fi

    # Run start-postgres.sh
    ./start-postgres.sh

    # Verify PostgreSQL is ready after startup
    echo ""
    echo "[*] Verifying PostgreSQL is ready..."
    MAX_RETRIES=30
    i=0
    until pg_isready -h "$DB_HOST" -p "$DB_PORT" -q 2>/dev/null; do
        i=$((i + 1))
        if [ $i -ge $MAX_RETRIES ]; then
            echo "[!] PostgreSQL failed to become ready after startup."
            exit 1
        fi
        echo "    Waiting for PostgreSQL... (attempt $i/$MAX_RETRIES)"
        sleep 2
    done
else
    echo "[✓] PostgreSQL is ready."
fi

echo ""

# Create virtual environment if it doesn't exist
VENV=".venv"
if [ ! -d "$VENV" ]; then
    echo "[*] Creating virtual environment in $VENV..."
    python3 -m venv "$VENV"
fi

# Activate virtual environment
echo "[*] Activating virtual environment..."
source "$VENV/bin/activate"

# Install/upgrade dependencies
echo "[*] Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo "[✓] Ready! Starting admin dashboard on http://127.0.0.1:8001"
echo ""

# Start the admin app (local-only, not exposed to the internet)
exec python -m uvicorn admin.app:app --host 127.0.0.1 --port 8001 --reload
