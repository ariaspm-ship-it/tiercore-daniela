# core/logger.py
# Sistema de logging centralizado

import logging
import sys
from pathlib import Path
from .config import Config

def setup_logger(name, level=None):
    """Configura y retorna un logger"""
    
    if level is None:
        level = getattr(logging, Config.LOG_LEVEL)
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Evitar duplicados
    if logger.handlers:
        return logger
    
    # Handler para consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_formatter = logging.Formatter(Config.LOG_FORMAT)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Handler para archivo
    log_file = Config.LOG_DIR / f"{name}.log"
    Config.LOG_DIR.mkdir(exist_ok=True)
    
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(level)
    file_formatter = logging.Formatter(Config.LOG_FORMAT)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    return logger

# Loggers predefinidos
main_logger = setup_logger("daniela")
devices_logger = setup_logger("devices")
protocols_logger = setup_logger("protocols")
ai_logger = setup_logger("ai")
simulator_logger = setup_logger("simulator")
