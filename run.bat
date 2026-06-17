@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

echo.
echo  ════════════════════════════════════
echo  SEX HEALTH NEWS
echo  ════════════════════════════════════
echo.

:: Check for .env file
if not exist .env (
    echo [!] No .env file found. Copy .env.example to .env and add your API keys.
    pause
    exit /b 1
)

:: Extract PostgreSQL host and port from .env
setlocal enabledelayedexpansion
for /f "tokens=2 delims==" %%a in ('findstr "^DATABASE_URL=" .env') do set "DB_URL=%%a"

:: Parse host and port (assuming postgresql+asyncpg://postgres:postgres@localhost:5432/...)
set "DB_HOST=localhost"
set "DB_PORT=5432"

if not "!DB_URL!"=="" (
    for /f "tokens=3 delims=@" %%a in ("!DB_URL!") do (
        set "HOST_PORT=%%a"
    )
    if not "!HOST_PORT!"=="" (
        for /f "tokens=1 delims=:" %%a in ("!HOST_PORT!") do set "DB_HOST=%%a"
        for /f "tokens=2 delims=:/" %%a in ("!HOST_PORT!") do set "DB_PORT=%%a"
    )
)

echo [*] Checking PostgreSQL at !DB_HOST!:!DB_PORT!...
set "PG_READY=0"
for /L %%i in (1,1,30) do (
    if !PG_READY!==0 (
        powershell -NoProfile -Command ^
            "try { $t=New-Object Net.Sockets.TcpClient; $t.Connect('!DB_HOST!', !DB_PORT!); $t.Close(); exit 0 } catch { exit 1 }" >nul 2>&1
        if !errorlevel!==0 (
            set "PG_READY=1"
        ) else (
            echo     Waiting for PostgreSQL... ^(attempt %%i/30^)
            timeout /t 2 /nobreak >nul
        )
    )
)

if !PG_READY!==0 (
    echo [!] PostgreSQL is not reachable at !DB_HOST!:!DB_PORT! after 30 attempts.
    echo     Run 'docker-compose up -d' to start PostgreSQL, or check your DATABASE_URL in .env
    pause
    exit /b 1
)
echo [OK] PostgreSQL is ready.

:: Create virtual environment if it doesn't exist
if not exist .venv (
    echo [*] Creating virtual environment...
    python -m venv .venv
    if !errorlevel! neq 0 (
        echo [!] Failed to create virtual environment.
        echo     Make sure Python 3.10+ is installed and in your PATH.
        pause
        exit /b 1
    )
)

:: Activate virtual environment
echo [*] Activating virtual environment...
call .venv\Scripts\activate.bat
if !errorlevel! neq 0 (
    echo [!] Failed to activate virtual environment.
    pause
    exit /b 1
)

:: Install/upgrade dependencies
echo [*] Installing dependencies...
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo [OK] Ready! Starting Sex Health News on http://0.0.0.0:8000
echo.

:: Start the app with auto-reload for development
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
