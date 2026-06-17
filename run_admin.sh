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

# Check if PostgreSQL is running with simple timeout test
is_postgres_running() {
    timeout 1 bash -c "echo >/dev/tcp/$DB_HOST/$DB_PORT" 2>/dev/null
}

# Check if PostgreSQL is ready
echo "[*] Checking PostgreSQL at $DB_HOST:$DB_PORT..."
if ! is_postgres_running; then
    echo "[!] PostgreSQL is not running."
    echo "[*] Attempting to start PostgreSQL with Docker..."

    # Check if start-postgres.sh exists
    if [ ! -f "start-postgres.sh" ]; then
        echo "[!] start-postgres.sh not found in current directory."
        exit 1
    fi

    # Run start-postgres.sh (which handles verification internally)
    ./start-postgres.sh

    # Add small delay to ensure PostgreSQL is fully ready for app startup
    sleep 2
else
    echo "[✓] PostgreSQL is already running."
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
