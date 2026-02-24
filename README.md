# TIERCORE - DANIELA v0.1

**Infrastructure Kernel for Critical Data Centers**

## ⚡ Quick Start (Windows)

1. **Conecta tu UPS por USB**
2. **Abre PowerShell como administrador**
3. **Ejecuta:**
	```powershell
	irm https://tiercore.run/windows | iex
	```

## 🛠 Scripts de operación (Windows)

Desde la raíz del proyecto:

```powershell
# Instalación inicial
powershell -ExecutionPolicy Bypass -File .\installer\install.ps1

# Actualizar código y servicios
powershell -ExecutionPolicy Bypass -File .\installer\update.ps1

# Verificar estado de servicios
powershell -ExecutionPolicy Bypass -File .\installer\healthcheck.ps1

# Desinstalar (con confirmación)
powershell -ExecutionPolicy Bypass -File .\installer\uninstall.ps1
```

