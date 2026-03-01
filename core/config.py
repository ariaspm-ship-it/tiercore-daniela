# core/config.py
# Configuración global del proyecto

import os
from pathlib import Path

class Config:
    """Configuración central de Daniela"""
    
    # Proyecto
    PROYECTO_NOMBRE = "BCH-VILLA COLONY RESORT"
    PROYECTO_VERSION = "0.5.0"
    
    # Rutas
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = BASE_DIR / "data"
    LOG_DIR = BASE_DIR / "logs"
    
    # Base de datos
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///daniela.db")
    
    # Protocolos
    BACNET_PORT = 47808
    MODBUS_TIMEOUT = 5
    MBUS_BAUDRATE = 2400
    
    # Simulación
    MODO_SIMULACION = True
    SIMULAR_FUGAS = True
    SIMULAR_CHILLERS = True
    
    # Umbrales
    UMBRAL_FUGA_LPH = 2.0  # Litros/hora
    UMBRAL_COP_MINIMO = 3.5
    UMBRAL_TEMP_MAXIMA = 28  # °C
    
    # Edificios
    EDIFICIOS = {
        "A": {"habitaciones": 119, "chillers": True},
        "B": {"habitaciones": 41, "chillers": False},
        "C": {"habitaciones": 27, "chillers": False},
        "V": {"villas": 4, "chillers": False}
    }
    
    # Logging
    LOG_LEVEL = "INFO"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    @classmethod
    def get_total_habitaciones(cls):
        return sum(b["habitaciones"] for b in cls.EDIFICIOS.values() if "habitaciones" in b)
    
    @classmethod
    def get_total_villas(cls):
        return cls.EDIFICIOS.get("V", {}).get("villas", 0)
    
    @classmethod
    def get_total_viviendas(cls):
        return cls.get_total_habitaciones() + cls.get_total_villas()
