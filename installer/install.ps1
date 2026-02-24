# Simple installer script for Windows Powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
# DANIELA - Instalador automático para Windows
# Ejecutar como administrador: irm https://tiercore.run | iex

Write-Host "╔═══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     DANIELA - INSTALACIÓN AUTOMÁTICA     ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# 1. Verificar PowerShell como administrador
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if (-not $isAdmin) {
	Write-Host "❌ Ejecuta PowerShell como administrador" -ForegroundColor Red
	exit 1
}

# 2. Verificar conexión a internet
try {
	$test = Test-Connection "8.8.8.8" -Count 1 -Quiet
	if (-not $test) { throw }
	Write-Host "✅ Internet: OK" -ForegroundColor Green
} catch {
	Write-Host "❌ Sin conexión a internet" -ForegroundColor Red
	exit 1
}

# 3. Instalar Chocolatey (gestor de paquetes)
Write-Host "`n📦 Instalando Chocolatey..." -ForegroundColor Yellow
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
refreshenv

# 4. Instalar dependencias
Write-Host "`n📦 Instalando Python y dependencias..." -ForegroundColor Yellow
choco install python docker-desktop git -y
refreshenv

# 5. Clonar repositorio
Write-Host "`n📦 Descargando Daniela..." -ForegroundColor Yellow
$repoUrl = "https://github.com/tiercore/daniela.git"
$installPath = "$env:USERPROFILE\daniela"
git clone $repoUrl $installPath
cd $installPath

# 6. Instalar NUT (Network UPS Tools)
Write-Host "`n📦 Configurando lector de UPS..." -ForegroundColor Yellow
choco install nut -y
Copy-Item "backend/drivers/*" "C:\Program Files\NUT\drivers\" -Force

# 7. Configurar entorno virtual Python
Write-Host "`n📦 Configurando entorno Python..." -ForegroundColor Yellow
python -m venv venv
.\venv\Scripts\activate
pip install -r backend/requirements.txt

# 8. Configurar Docker y base de datos
Write-Host "`n📦 Iniciando base de datos..." -ForegroundColor Yellow
docker-compose up -d

# 9. Iniciar Daniela
Write-Host "`n🚀 Iniciando Daniela..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd $installPath\backend; python main.py"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd $installPath\frontend; python -m http.server 3000"

Write-Host ""
Write-Host "╔═══════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  ✅ DANIELA INSTALADA                     ║" -ForegroundColor Green
Write-Host "╠═══════════════════════════════════════════╣" -ForegroundColor Green
Write-Host "║  Abre tu navegador en:                    ║" -ForegroundColor White
Write-Host "║  http://localhost:3000                    ║" -ForegroundColor Cyan
Write-Host "║                                            ║" -ForegroundColor White
Write-Host "║  Tu UPS debe estar conectado por USB      ║" -ForegroundColor Yellow
Write-Host "╚═══════════════════════════════════════════╝" -ForegroundColor Green