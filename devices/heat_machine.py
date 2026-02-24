# devices/heat_machine.py
# Clase Heat Machine CXAU (2 unidades)

from dataclasses import dataclass
from datetime import datetime
from core.logger import devices_logger

@dataclass
class HeatMachineData:
    """Datos de una heat machine"""
    timestamp: datetime
    temp_supply: float       # Temperatura impulsión ACS
    temp_return: float       # Temperatura retorno
    power_kw: float          # Consumo eléctrico
    heating_kw: float        # Calor producido
    efficiency: float        # Eficiencia (COP térmico)
    pump_status: int         # Estado bombas
    alarm: bool

class HeatMachine:
    """Representa una heat machine CXAU para ACS"""
    
    def __init__(self, machine_id, nombre, ip):
        self.id = machine_id     # ej: "CXAU-1"
        self.nombre = nombre
        self.ip = ip
        self.ubicacion = "Production Roof"
        self.history = []
        self.last_data = None
        
        devices_logger.info(f"Heat Machine {self.id} inicializada")
    
    def update(self, data: HeatMachineData):
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
            "temp_supply": self.last_data.temp_supply,
            "temp_return": self.last_data.temp_return,
            "power_kw": self.last_data.power_kw,
            "heating_kw": self.last_data.heating_kw,
            "efficiency": self.last_data.efficiency,
            "pump_status": self.last_data.pump_status,
            "alarm": self.last_data.alarm,
            "timestamp": self.last_data.timestamp.isoformat()
        }
