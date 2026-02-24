#!/usr/bin/env python3
# DANIELA - Backend API Server v1.0

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import threading
import json
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List
import os

from ups_reader import UPSReader
from ia_engine import IAEngine

# Inicializar componentes
app = FastAPI(title="Daniela API", description="TierCore - Infrastructure Kernel")
ups = UPSReader()
ia = IAEngine(use_deepseek=True)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base de datos temporal (en memoria)
current_data = {}
analysis_cache = {}
last_analysis = None

# Modelos
class BatteryChange(BaseModel):
    ups_id: str
    change_date: str
    battery_type: str
    notes: Optional[str] = None

class Alert(BaseModel):
    id: str
    type: str
    severity: str
    text: str
    timestamp: str
    acknowledged: bool = False

# Inicializar UPS
def init_ups():
    global current_data
    if ups.find_ups():
        print(f"✅ UPS encontrado: {ups.manufacturer} {ups.product}")
    else:
        print("⚠️ No se encontró UPS físico. Usando modo simulación.")
    
    def data_callback(data):
        global current_data, analysis_cache, last_analysis
        current_data = data
        current_data["timestamp"] = datetime.now().isoformat()
        
        # Añadir a IA para análisis
        ia.add_reading(data)
        
        # Analizar cada 60 segundos
        now = datetime.now()
        if last_analysis is None or (now - last_analysis).seconds > 60:
            analysis_cache = ia.analyze()
            last_analysis = now
    
    ups.start_monitoring(data_callback)

# Endpoints
@app.get("/")
async def root():
    return {
        "service": "Daniela - TierCore Infrastructure Kernel",
        "version": "0.1.0",
        "status": "operational"
    }

@app.get("/api/v1/ups")
async def get_all_ups():
    """Lista todos los UPS detectados"""
    return {
        "ups": [{
            "id": "ups-01",
            "name": f"{ups.manufacturer} {ups.product}",
            "location": "Oficina principal",
            "status": current_data.get("status", "unknown"),
            "last_update": current_data.get("last_update", datetime.now().isoformat())
        }],
        "total": 1
    }

@app.get("/api/v1/ups/{ups_id}")
async def get_ups_detail(ups_id: str):
    """Detalle de un UPS específico"""
    if ups_id != "ups-01":
        raise HTTPException(status_code=404, detail="UPS no encontrado")
    
    return {
        "id": ups_id,
        "name": f"{ups.manufacturer} {ups.product}",
        "serial": ups.serial,
        "data": current_data,
        "analysis": analysis_cache
    }

@app.get("/api/v1/alerts")
async def get_alerts(acknowledged: bool = False):
    """Lista todas las alertas"""
    alerts = []
    for alert in ia.alerts:
        if not acknowledged and alert.get("acknowledged", False):
            continue
        alerts.append({
            "id": f"alert-{len(alerts)}",
            "type": alert["type"],
            "severity": alert["severity"],
            "text": alert["text"],
            "timestamp": alert["timestamp"],
            "acknowledged": alert.get("acknowledged", False)
        })
    return {"alerts": alerts[-20:]}  # últimas 20

@app.post("/api/v1/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """Marcar alerta como vista"""
    # En implementación real, buscar por ID
    if ia.alerts:
        ia.alerts[-1]["acknowledged"] = True
    return {"status": "ok"}

@app.post("/api/v1/battery/replaced")
async def register_battery_change(change: BatteryChange):
    """Registrar cambio de baterías"""
    # Guardar en archivo/localstorage
    record = {
        "ups_id": change.ups_id,
        "change_date": change.change_date,
        "battery_type": change.battery_type,
        "notes": change.notes,
        "registered_at": datetime.now().isoformat()
    }
    
    # Guardar a disco
    try:
        with open("battery_changes.json", "a") as f:
            f.write(json.dumps(record) + "\n")
    except:
        pass
    
    return {"status": "ok", "record": record}

@app.get("/api/v1/predictions")
async def get_predictions():
    """Obtener predicciones de IA"""
    return analysis_cache.get("predictions", {})

@app.get("/api/v1/health")
async def health_check():
    """Health check del sistema"""
    return {
        "status": "healthy",
        "ups_connected": ups.device is not None,
        "last_update": current_data.get("last_update"),
        "alerts_count": len(ia.alerts)
    }

# Iniciar en segundo plano
threading.Thread(target=init_ups, daemon=True).start()

if __name__ == "__main__":
    print("🚀 Iniciando Daniela backend...")
    uvicorn.run(app, host="0.0.0.0", port=8000)