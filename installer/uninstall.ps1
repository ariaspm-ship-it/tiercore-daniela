param(
    [switch]$Force,
    [string]$InstallPath = "$env:USERPROFILE\daniela"
)

$ErrorActionPreference = "Stop"

if (-not $Force) {
    $confirmation = Read-Host "Esto detendrá servicios y puede borrar archivos en '$InstallPath'. ¿Continuar? (yes/no)"
    if ($confirmation -ne "yes") {
        Write-Host "Cancelado por el usuario." -ForegroundColor Yellow
        exit 0
    }
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

if (Test-Path "docker-compose.yml") {
    Write-Host "🐳 Deteniendo y limpiando servicios Docker..." -ForegroundColor Yellow
    docker-compose down -v
}

if (Test-Path "$repoRoot\venv") {
    Write-Host "🧹 Eliminando entorno virtual local..." -ForegroundColor Yellow
    Remove-Item -LiteralPath "$repoRoot\venv" -Recurse -Force
}

if ((Test-Path $InstallPath) -and ($InstallPath -ne $repoRoot.Path)) {
    Write-Host "🧹 Eliminando carpeta instalada..." -ForegroundColor Yellow
    Remove-Item -LiteralPath $InstallPath -Recurse -Force
}

Write-Host "✅ Desinstalación finalizada" -ForegroundColor Green
