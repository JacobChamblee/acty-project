@echo off
REM ═══════════════════════════════════════════════════════════════════════════════
REM Acty Project - Deployment Quick Start (Windows)
REM ═══════════════════════════════════════════════════════════════════════════════
REM
REM This script automates the deployment verification and startup process.
REM Usage: deploy.bat [dev|prod]
REM ═══════════════════════════════════════════════════════════════════════════════

setlocal enabledelayedexpansion

set ENVIRONMENT=%1
if "%ENVIRONMENT%"=="" set ENVIRONMENT=dev
set PROJECT_ROOT=%~dp0

echo ═══════════════════════════════════════════════════════════════════════════════
echo Acty Project Deployment - %ENVIRONMENT% Environment
echo ═══════════════════════════════════════════════════════════════════════════════
echo.

REM ── Step 1: Verify Prerequisites ──────────────────────────────────────────────
echo Step 1: Verifying prerequisites...

where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker not found. Install from https://docs.docker.com/get-docker/
    exit /b 1
)
for /f "tokens=3" %%i in ('docker --version') do set DOCKER_VERSION=%%i
echo [OK] Docker installed (%DOCKER_VERSION%)

where docker-compose >nul 2>&1
if %errorlevel% neq 0 (
    where docker >nul 2>&1
    if %errorlevel% equ 0 (
        docker -v | findstr "version" >nul
        if %errorlevel% equ 0 (
            echo [OK] Docker Compose available
        )
    )
)

if not exist "%PROJECT_ROOT%.env" (
    echo [WARN] .env file not found. Creating from .env.example...
    if exist "%PROJECT_ROOT%.env.example" (
        copy "%PROJECT_ROOT%.env.example" "%PROJECT_ROOT%.env" >nul
        echo [WARN] Please edit .env with your configuration before deploying
    ) else (
        echo [ERROR] .env.example not found
        exit /b 1
    )
)

if not exist "%PROJECT_ROOT%docker-compose.yml" (
    echo [ERROR] docker-compose.yml not found
    exit /b 1
)
echo [OK] docker-compose.yml found
echo [OK] All prerequisites verified
echo.

REM ── Step 2: Build Docker Images ───────────────────────────────────────────────
echo Step 2: Building Docker images...
cd /d "%PROJECT_ROOT%"
docker compose build --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Docker build failed
    exit /b 1
)
echo [OK] Docker images built successfully
echo.

REM ── Step 3: Start Services ────────────────────────────────────────────────────
echo Step 3: Starting services...
docker compose up -d
if %errorlevel% neq 0 (
    echo [ERROR] Failed to start services
    exit /b 1
)
echo [OK] Services started
echo.

REM ── Step 4: Wait for Services ────────────────────────────────────────────────
echo Step 4: Waiting for services to be healthy ^(max 30s^)...
timeout /t 5 /nobreak >nul
echo [OK] Services initialized
echo.

REM ── Step 5: Display Status ───────────────────────────────────────────────────
echo Step 5: Checking service status...
docker compose ps
echo.

REM ── Step 6: Display Service Endpoints ─────────────────────────────────────────
echo ═══════════════════════════════════════════════════════════════════════════════
echo Deployment Complete!
echo ═══════════════════════════════════════════════════════════════════════════════
echo.

echo Service Endpoints:
echo   API               : http://localhost:8765
echo   API Docs          : http://localhost:8765/docs
echo   Grafana Dashboard : http://localhost:3000 ^(admin/admin^)
echo   Database          : postgres://localhost:5432
echo.

echo Useful Commands:
echo   View logs         : docker compose logs -f api
echo   Check status      : docker compose ps
echo   Stop services     : docker compose down
echo   Restart API       : docker compose restart api
echo.

echo Deployment Docs:
echo   Full checklist    : type DEPLOYMENT_CHECKLIST.md
echo   Configuration    : type .env.example
echo   API Reference     : http://localhost:8765/docs
echo.

echo Next Steps:
echo   1. Review .env configuration
echo   2. Load OBD CSV data via API
echo   3. Monitor via Grafana dashboard
echo   4. Review deployment checklist before production
echo.

echo [OK] Waiting 3 seconds before closing...
timeout /t 3 /nobreak >nul
