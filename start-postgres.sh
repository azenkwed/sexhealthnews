#!/usr/bin/env bash
set -euo pipefail

echo ""
echo " ════════════════════════════════════"
echo " Starting PostgreSQL with Docker"
echo " ════════════════════════════════════"
echo ""

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    echo "[!] Docker is not installed."
    echo "    Install Docker from: https://www.docker.com/products/docker-desktop"
    exit 1
fi
echo "[✓] Docker is installed"

# Check if docker daemon is running
if ! docker ps &> /dev/null; then
    echo "[!] Docker daemon is not running."
    echo "    Start Docker Desktop or the Docker daemon and try again."
    exit 1
fi
echo "[✓] Docker daemon is running"

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "[!] docker-compose is not installed."
    echo "    Install Docker Desktop (includes docker-compose) or install it separately."
    exit 1
fi
echo "[✓] docker-compose is available"

# Check if docker-compose.yml exists
if [ ! -f "docker-compose.yml" ]; then
    echo "[!] docker-compose.yml not found in current directory."
    echo "    Make sure you're in the project root directory."
    exit 1
fi

# Start PostgreSQL containers
echo ""
echo "[*] Starting PostgreSQL and pgAdmin containers..."
docker-compose up -d

# Wait for PostgreSQL to be ready
echo ""
echo "[*] Waiting for PostgreSQL to be ready..."
MAX_RETRIES=30
i=0
until docker-compose exec -T db pg_isready -U postgres -d sexhealthnews &> /dev/null; do
    i=$((i + 1))
    if [ $i -ge $MAX_RETRIES ]; then
        echo "[!] PostgreSQL failed to become ready after ${MAX_RETRIES} attempts."
        echo "    Check logs with: docker-compose logs db"
        exit 1
    fi
    echo "    Waiting for PostgreSQL... (attempt $i/$MAX_RETRIES)"
    sleep 2
done

echo ""
echo "[✓] PostgreSQL is ready!"
echo ""
echo "📊 Available services:"
echo "   PostgreSQL:  localhost:5432 (user: postgres, password: postgres, db: sexhealthnews)"
echo "   pgAdmin:     http://localhost:5050 (user: admin@localhost, password: admin)"
echo ""
echo "[*] You can now run './run.sh' to start the application."
echo ""
