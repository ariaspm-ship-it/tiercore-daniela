# devices/inverter.py
# Clase Inversor solar (5 unidades: A:2, C:3)

from dataclasses import dataclass
from datetime import datetime
from core.logger import devices_logger

@dataclass
class InverterData:
    """Datos de un inversor solar"""
    timestamp: datetime
    power_kw: float           # Potencia generada
    voltage: float            # Tensión DC
    current: float            # Corriente DC
    grid_power_kw: float      # Potencia a red
    temperature: float        # Temperatura inversor
    efficiency: float         # Eficiencia %
    status: str               # Funcionando / Standby / Falla

class Inverter:
    """Representa un inversor fotovoltaico"""
    
    def __init__(self, inv_id, nombre, ubicacion):
        self.id = inv_id           # ej: "INV-A1"
        self.nombre = nombre
        self.ubicacion = ubicacion
        self.history = []
        self.last_data = None
        
        devices_logger.info(f"Inversor {self.id} inicializado")
    
    def update(self, data: InverterData):
        self.last_data = data
        self.history.append(data)
        
        if len(self.history) > 1000:
            self.history = self.history[-1000:]
    
    def get_status(self):
        if not self.last_data:
            return {"estado": "sin_datos", "id": self.id}
        
        return {
            "id": self.id,
            "nombre": self.nombre,
            "ubicacion": self.ubicacion,
            "power_kw": self.last_data.power_kw,
            "grid_power_kw": self.last_data.grid_power_kw,
            "temperature": self.last_data.temperature,
            "efficiency": self.last_data.efficiency,
            "status": self.last_data.status,
            "timestamp": self.last_data.timestamp.isoformat()
        }
    
    def get_daily_yield(self):
        """Producción acumulada hoy"""
        if not self.history:
            return 0
        
        # Simplificado para prototipo
        hoy = datetime.now().date()
        lecturas_hoy = [d for d in self.history if d.timestamp.date() == hoy]
        
        if not lecturas_hoy:
            return 0
        
        # Asumiendo lecturas cada hora
        return sum(d.power_kw for d in lecturas_hoy) / 1000  # kWh
