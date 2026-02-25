# devices/chiller.py
# Clase Chiller RTAG (basado en 2CH-1,2,3)

from dataclasses import dataclass
from typing import Dict, Optional
from datetime import datetime
from core.logger import devices_logger

@dataclass
class ChillerData:
    """Datos de un chiller en un momento dado"""
    timestamp: datetime
    temp_supply: Optional[float]  # Temperatura impulsión °C
    temp_return: Optional[float]   # Temperatura retorno °C
    power_kw: Optional[float]      # Consumo eléctrico kW
    cooling_kw: Optional[float]    # Frío producido kW
    cop: Optional[float]           # Coeficiente de rendimiento
    compressor_status: int          # Estado compresores (bitmask)
    alarm: bool                     # Alarma activa
    flow_m3h: Optional[float]       # Caudal m³/h

class Chiller:
    """Representa un chiller RTAG del proyecto"""
    
    def __init__(self, chiller_id, nombre, ip, protocolo="BACnet/IP"):
        self.id = chiller_id          # ej: "2CH-1"
        self.nombre = nombre          # ej: "Chiller RTAG-01"
        self.ip = ip
        self.protocolo = protocolo
        self.ubicacion = "Roof Building A"
        self.history = []
        self.last_data = None
        
        devices_logger.info(f"Chiller {self.id} inicializado")
    
    def update(self, data: ChillerData):
        """Actualiza con nueva lectura"""
        self.last_data = data
        self.history.append(data)
        
        # Mantener solo últimas 1000 lecturas
        if len(self.history) > 1000:
            self.history = self.history[-1000:]
        
        cop_text = f"{data.cop:.2f}" if data.cop is not None else "N/A"
        devices_logger.debug(f"Chiller {self.id} actualizado: {cop_text} COP")
    
    def calculate_cop(self, temp_supply, temp_return, flow_m3h, power_kw):
        """Calcula COP si no viene directamente"""
        if None in [temp_supply, temp_return, flow_m3h, power_kw] or power_kw == 0:
            return None
        
        # Fórmula: COP = (caudal * deltaT * 1.16) / potencia
        delta_t = temp_return - temp_supply
        cooling_kw = flow_m3h * delta_t * 1.16
        cop = cooling_kw / power_kw
        
        return round(cop, 2)
    
    def get_status(self):
        """Retorna estado actual para dashboard"""
        if not self.last_data:
            return {"estado": "sin_datos", "id": self.id}
        
        return {
            "id": self.id,
            "nombre": self.nombre,
            "temp_supply": self.last_data.temp_supply,
            "temp_return": self.last_data.temp_return,
            "power_kw": self.last_data.power_kw,
            "cop": self.last_data.cop,
            "alarm": self.last_data.alarm,
            "timestamp": self.last_data.timestamp.isoformat(),
            "estado": "alarma" if self.last_data.alarm else "ok"
        }
    
    def get_hours_run(self):
        """Calcula horas de funcionamiento (simulado)"""
        if len(self.history) < 2:
            return 0
        
        # Versión simplificada para prototipo
        return len(self.history) * 5 / 60  # horas aproximadas
