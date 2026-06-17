@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

echo.
echo  ════════════════════════════════════
echo  Starting PostgreSQL with Docker
echo  ════════════════════════════════════
echo.

:: Check if docker is installed
where docker >nul 2>&1
if !errorlevel! neq 0 (
    echo [!] Docker is not installed.
    echo     Install Docker Desktop from: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)
echo [OK] Docker is installed

:: Check if docker daemon is running
docker ps >nul 2>&1
if !errorlevel! neq 0 (
    echo [!] Docker daemon is not running.
    echo     Start Docker Desktop and try again.
    pause
    exit /b 1
)
echo [OK] Docker daemon is running

:: Check if docker-compose is available
where docker-compose >nul 2>&1
if !errorlevel! neq 0 (
    echo [!] docker-compose is not installed.
    echo     Install Docker Desktop ^(includes docker-compose^) or install it separately.
    pause
    exit /b 1
)
echo [OK] docker-compose is available

:: Check if docker-compose.yml exists
if not exist docker-compose.yml (
    echo [!] docker-compose.yml not found in current directory.
    echo     Make sure you're in the project root directory.
    pause
    exit /b 1
)

:: Start PostgreSQL containers
echo.
echo [*] Starting PostgreSQL and pgAdmin containers...
docker-compose up -d
if !errorlevel! neq 0 (
    echo [!] Failed to start containers.
    echo     Check Docker Desktop logs for details.
    pause
    exit /b 1
)

:: Wait for PostgreSQL to be ready
echo.
echo [*] Waiting for PostgreSQL to be ready...
set "PG_READY=0"
for /L %%i in (1,1,30) do (
    if !PG_READY!==0 (
        docker-compose exec -T db pg_isready -U postgres -d sexhealthnews >nul 2>&1
        if !errorlevel!==0 (
            set "PG_READY=1"
        ) else (
            echo     Waiting for PostgreSQL... ^(attempt %%i/30^)
            timeout /t 2 /nobreak >nul
        )
    )
)

if !PG_READY!==0 (
    echo [!] PostgreSQL failed to become ready after 30 attempts.
    echo     Check logs with: docker-compose logs db
    pause
    exit /b 1
)

echo.
echo [OK] PostgreSQL is ready!
echo.
echo 📊 Available services:
echo    PostgreSQL:  localhost:5432 ^(user: postgres, password: postgres, db: sexhealthnews^)
echo    pgAdmin:     http://localhost:5050 ^(user: admin@sexhealthnews.local, password: admin^)
echo.
echo [*] You can now run 'run.bat' to start the application.
echo.
pause
