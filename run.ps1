# AI Anime Companion — Lệnh dev trên Windows (thay cho make)
# Cách dùng: .\run.ps1 <lệnh>   ví dụ: .\run.ps1 dev

param(
    [Parameter(Position = 0)]
    [string] $Command = "help"
)

$ErrorActionPreference = "Stop"

switch ($Command.ToLower()) {
    "help" {
        Write-Host "=== AI Anime Companion — Development Commands ===" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "  .\run.ps1 dev       - Chạy Docker Compose (PostgreSQL, Redis, ChromaDB)"
        Write-Host "  .\run.ps1 down      - Dừng Docker Compose"
        Write-Host "  .\run.ps1 setup     - Cài dependencies (pip install -r requirements.txt)"
        Write-Host "  .\run.ps1 run-core   - Chạy Core API local (uvicorn)"
        Write-Host "  .\run.ps1 test      - Chạy pytest"
        Write-Host "  .\run.ps1 lint      - Chạy ruff"
    }
    "dev" {
        docker compose up --build
    }
    "down" {
        docker compose down
    }
    "setup" {
        Write-Host "Installing dependencies..."
        pip install -r requirements.txt
        if (Test-Path "ml/requirements-training.txt") {
            Write-Host "Installing ML Training dependencies..."
            pip install -r ml/requirements-training.txt
        }
    }
    "run-core" {
        Write-Host "Starting Core Service..."
        uvicorn services.core.main:app --reload --host 0.0.0.0 --port 8000
    }
    "test" {
        pytest services/ -v
    }
    "lint" {
        ruff check services/ shared/ ml/
    }
    default {
        Write-Host "Lệnh không rõ. Chạy: .\run.ps1 help"
        exit 1
    }
}
