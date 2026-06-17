@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
echo.
echo  ========================
echo  FLESH PULSE
echo  ========================
echo.

if not exist .env (
    echo [!] No .env file found. Copy .env.example to .env and add your API keys.
    pause
    exit /b 1
)

:: ── PostgreSQL check ─────────────────────────────────────────────────────────
echo [*] Checking PostgreSQL on localhost:5432...
set PG_READY=0
for /L %%i in (1,1,5) do (
    if !PG_READY!==0 (
        powershell -NoProfile -Command ^
            "try { $t=New-Object Net.Sockets.TcpClient; $t.Connect('localhost',5432); $t.Close(); exit 0 } catch { exit 1 }" >nul 2>&1
        if !errorlevel!==0 (
            set PG_READY=1
        ) else (
            echo     Waiting for PostgreSQL... (attempt %%i/5^)
            timeout /t 2 /nobreak >nul
        )
    )
)
if !PG_READY!==0 (
    echo [!] PostgreSQL is not reachable on localhost:5432 after 5 attempts.
    echo     Run 'make db' to start it, or check your DATABASE_URL in .env
    pause
    exit /b 1
)
echo [OK] PostgreSQL is ready.

if not exist .venv (
    echo [*] Creating virtual environment...
    python -m venv .venv
)

echo [*] Activating virtual environment...
call .venv\Scripts\activate.bat

echo [*] Installing dependencies...
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
