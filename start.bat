@echo off
setlocal

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

echo Starting FaceFind...
echo Project root: %ROOT%

if not exist "%ROOT%\.env" (
    if exist "%ROOT%\.env.example" (
        copy "%ROOT%\.env.example" "%ROOT%\.env" >nul
        echo Created .env from .env.example
    )
)

echo.
echo Starting Postgres and Redis (docker compose)...
where docker >nul 2>nul
if errorlevel 1 (
    echo Docker not found on PATH - skipping. Make sure Postgres/Redis are reachable some other way.
) else (
    docker compose -f "%ROOT%\docker-compose.yml" up -d db redis
)

echo.
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo Backend already running at http://localhost:8000
) else (
    echo Starting backend at http://localhost:8000
    pushd "%ROOT%"
    set "PYTHONPATH=%ROOT%\backend"
    start "FaceFind Backend" cmd /k "python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
    popd
)

netstat -ano | findstr ":5173" | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo Frontend already running at http://localhost:5173
) else (
    echo Starting frontend at http://localhost:5173
    pushd "%ROOT%\frontend"
    if not exist node_modules (
        echo Installing frontend dependencies...
        call npm.cmd install
    )
    start "FaceFind Frontend" cmd /k "npm.cmd run dev"
    popd
)

echo.
echo FaceFind is starting in two terminal windows.
echo Frontend: http://localhost:5173
echo Backend:  http://localhost:8000

endlocal
