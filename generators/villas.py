# generators/villas.py
# Generador de las 4 villas según plano M-2-SLD-1

from devices.room import Room
from dataclasses import dataclass
from datetime import datetime

@dataclass
class VillaData:
    """Datos de una villa (ampliado respecto a habitación)"""
    timestamp: datetime
    electricity_kwh: float
    water_cold_m3: float
    water_hot_m3: float
    pool_kwh: float          # Consumo piscina privada
    irrigation_m3: float     # Consumo riego
    fuga_detectada: bool = False

class Villa(Room):
    """Representa una villa (hereda de Room pero con más atributos)"""
    
    def __init__(self, villa_id, nombre):
        super().__init__(villa_id, "V", 0)
        self.nombre = nombre
        self.piscina_activa = True
        self.jardin_m2 = 300 + int(villa_id[-1]) * 50
        
    def update(self, data: VillaData):
        """Actualiza con datos específicos de villa"""
        self.last_data = data
        self.history.append(data)
        
        if len(self.history) > 1000:
            self.history = self.history[-1000:]
    
    def get_status(self):
        """Estado ampliado para villa"""
        base = super().get_status()
        if not self.last_data:
            return base
        
        base.update({
            "nombre": self.nombre,
            "pool_kwh": self.last_data.pool_kwh,
            "irrigation_m3": self.last_data.irrigation_m3,
            "piscina_activa": self.piscina_activa,
            "jardin_m2": self.jardin_m2
        })
        return base

def generar_villas():
    """Genera las 4 villas"""
    
    villas = []
    for i in range(1, 5):
        villa = Villa(f"V{i:02d}", f"Villa {i}")
        villas.append(villa)
    
    print(f"{len(villas)} villas generadas")
    return villas

# Generar al importar
VILLAS = generar_villas()
