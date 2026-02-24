param(
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

Write-Host "📦 Actualizando código desde origin/$Branch..." -ForegroundColor Yellow
git fetch origin
git checkout $Branch
git pull origin $Branch

if (Test-Path "backend/requirements.txt") {
    Write-Host "🐍 Actualizando dependencias de backend..." -ForegroundColor Yellow
    python -m pip install -r "backend/requirements.txt"
}

if (Test-Path "docker-compose.yml") {
    Write-Host "🐳 Actualizando servicios Docker..." -ForegroundColor Yellow
    docker-compose pull
    docker-compose up -d --build
}

Write-Host "✅ Actualización completada" -ForegroundColor Green
