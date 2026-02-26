# DANIELA · Investor Demo Runbook (Windows)

## 1) Pre-check (2-3 min)

```powershell
Set-Location "c:\Users\OliverGonzalez\OneDrive - CONSTRUCCIONES ROQUE NUBLO SRL\Documents\Tier\tiercore-daniela"
& "c:/Users/OliverGonzalez/OneDrive - CONSTRUCCIONES ROQUE NUBLO SRL/Documents/Tier/tiercore-daniela/backend/.venv/Scripts/python.exe" demo_investors.py --test --no-slow
```

Si este comando corre completo, estás listo para grabar.

## 2) Demo de grabación (5 min)

```powershell
Set-Location "c:\Users\OliverGonzalez\OneDrive - CONSTRUCCIONES ROQUE NUBLO SRL\Documents\Tier\tiercore-daniela"
& "c:/Users/OliverGonzalez/OneDrive - CONSTRUCCIONES ROQUE NUBLO SRL/Documents/Tier/tiercore-daniela/backend/.venv/Scripts/python.exe" demo_investors.py
```

## 3) Demo con Claude real (opcional)

```powershell
$env:ANTHROPIC_API_KEY="sk-ant-..."
& "c:/Users/OliverGonzalez/OneDrive - CONSTRUCCIONES ROQUE NUBLO SRL/Documents/Tier/tiercore-daniela/backend/.venv/Scripts/python.exe" -m ai.claude_agent
```

## 4) Checklist de grabación

- Micrófono probado
- Pantalla limpia (sin datos personales)
- Terminal maximizada y tema oscuro
- `demo_investors.py` ejecutando sin errores
- Pitch deck abierto en pestaña aparte
- One-pager listo para enviar

## 5) Salida esperada

- Escena 1: vista global de resort
- Escena 2: optimización de chillers con ahorro potencial
- Escena 3: detección de fugas
- Escena 4: conversación con Daniela
- Escena 5: proyección a data centers + call to action
