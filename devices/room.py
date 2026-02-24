# devices/room.py
# Clase Habitación (187 unidades)

from dataclasses import dataclass
from typing import Dict, Optional
from datetime import datetime, time
from core.logger import devices_logger

@dataclass
class RoomData:
    """Datos de una habitación"""
    timestamp: datetime
    electricity_kwh: float
    water_cold_m3: float
    water_hot_m3: float
    fc_kwh: float
    return_temp: float
    fuga_detectada: bool = False

class Room:
    """Representa una habitación del resort"""
    
    def __init__(self, room_id, edificio, planta):
        self.id = room_id          # ej: "A301"
        self.edificio = edificio
        self.planta = planta
        self.history = []
        self.last_data = None
        self.fuga_activa = False
        
        devices_logger.info(f"Habitación {self.id} inicializada")
    
    def update(self, data: RoomData):
        """Actualiza con nueva lectura"""
        self.last_data = data
        self.history.append(data)
        self.fuga_activa = data.fuga_detectada
        
        if len(self.history) > 1000:
            self.history = self.history[-1000:]
        
        if data.fuga_detectada:
            devices_logger.warning(f"⚠️ FUGA DETECTADA en {self.id}")
    
    def get_night_flow(self):
        """Calcula caudal nocturno (2am-5am) para detectar fugas"""
        if len(self.history) < 10:
            return 0
        
        night_readings = []
        for data in self.history[-50:]:  # últimas 50 lecturas
            hora = data.timestamp.hour
            if 2 <= hora <= 5:
                night_readings.append(data.water_cold_m3 * 1000)  # convertir a litros
        
        if not night_readings:
            return 0
        
        return sum(night_readings) / len(night_readings) * 12  # litros/hora aproximado
    
    def get_status(self):
        """Retorna estado actual para dashboard"""
        if not self.last_data:
            return {"estado": "sin_datos", "id": self.id}
        
        night_flow = self.get_night_flow()
        fuga_probable = night_flow > 2.0  # umbral 2 litros/hora
        
        return {
            "id": self.id,
            "edificio": self.edificio,
            "planta": self.planta,
            "electricidad_hoy": self.last_data.electricity_kwh,
            "agua_hoy": self.last_data.water_cold_m3,
            "acs_hoy": self.last_data.water_hot_m3,
            "fuga_activa": self.last_data.fuga_detectada or fuga_probable,
            "night_flow_lph": round(night_flow, 1),
            "timestamp": self.last_data.timestamp.isoformat()
        }
    
    def get_consumo_medio(self, days=30):
        """Calcula consumo medio de los últimos días"""
        if len(self.history) < days:
            return None
        
        recent = self.history[-days:]
        return {
            "electricidad": sum(d.electricity_kwh for d in recent) / days,
            "agua": sum(d.water_cold_m3 for d in recent) / days,
            "acs": sum(d.water_hot_m3 for d in recent) / days
        }
