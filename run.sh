#!/usr/bin/env bash
set -euo pipefail

echo ""
echo " ========================"
echo " FLESH PULSE"
echo " ========================"
echo ""

if [ ! -f .env ]; then
    echo "[!] No .env file found. Copy .env.example to .env and add your API keys."
    exit 1
fi

# ── PostgreSQL check ──────────────────────────────────────────────────────────
DB_URL="${DATABASE_URL:-$(grep -E '^DATABASE_URL=' .env 2>/dev/null | cut -d= -f2-)}"
DB_HOST=$(echo "$DB_URL" | sed -E 's|.*@([^:/]+).*|\1|')
DB_PORT=$(echo "$DB_URL" | sed -E 's|.*:([0-9]+)/.*|\1|')
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

echo "[*] Checking PostgreSQL at $DB_HOST:$DB_PORT..."
MAX_RETRIES=5
i=0
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -q 2>/dev/null; do
    i=$((i + 1))
    if [ $i -ge $MAX_RETRIES ]; then
        echo "[!] PostgreSQL is not reachable at $DB_HOST:$DB_PORT after ${MAX_RETRIES} attempts."
        echo "    Run 'make db' to start it, or check your DATABASE_URL in .env"
        exit 1
    fi
    echo "    Waiting for PostgreSQL... (attempt $i/$MAX_RETRIES)"
    sleep 2
done
echo "[✓] PostgreSQL is ready."

VENV=".venv"

if [ ! -d "$VENV" ]; then
    echo "[*] Creating virtual environment..."
    python3 -m venv "$VENV"
fi

echo "[*] Activating virtual environment..."
source "$VENV/bin/activate"

echo "[*] Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

exec python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
