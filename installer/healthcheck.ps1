$ErrorActionPreference = "Stop"

function Test-Port {
    param(
        [string]$Host,
        [int]$Port,
        [string]$Name
    )

    try {
        $ok = Test-NetConnection -ComputerName $Host -Port $Port -InformationLevel Quiet
        if ($ok) {
            Write-Host "✅ $Name ($Host`:$Port)" -ForegroundColor Green
            return $true
        }

        Write-Host "❌ $Name ($Host`:$Port)" -ForegroundColor Red
        return $false
    }
    catch {
        Write-Host "❌ $Name ($Host`:$Port)" -ForegroundColor Red
        return $false
    }
}

Write-Host "🔎 Healthcheck DANIELA" -ForegroundColor Cyan

$allGood = $true

$allGood = (Test-Port -Host "localhost" -Port 8000 -Name "Backend API") -and $allGood
$allGood = (Test-Port -Host "localhost" -Port 8086 -Name "InfluxDB") -and $allGood
$allGood = (Test-Port -Host "localhost" -Port 6379 -Name "Redis") -and $allGood
$allGood = (Test-Port -Host "localhost" -Port 3001 -Name "Grafana") -and $allGood

if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Host "\n🐳 Estado de contenedores:" -ForegroundColor Yellow
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

if ($allGood) {
    Write-Host "\n✅ Todos los servicios principales responden" -ForegroundColor Green
    exit 0
}

Write-Host "\n⚠️ Hay servicios que no están respondiendo" -ForegroundColor Yellow
exit 1
