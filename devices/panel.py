# devices/panel.py
# Clase Panel Eléctrico (MDP, cuadros secundarios)

from dataclasses import dataclass
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import numpy as np

from core.logger import devices_logger


@dataclass
class PanelData:
    """Datos de un panel eléctrico en un momento dado"""
    timestamp: datetime
    voltage_l1: float
    voltage_l2: float
    voltage_l3: float
    current_l1: float
    current_l2: float
    current_l3: float
    power_kw: float
    power_factor: Optional[float] = None
    frequency: Optional[float] = 60.0
    alarm: bool = False
    breaker_status: int = 1


class ElectricalPanel:
    """Representa un panel eléctrico del edificio"""

    TIPOS = {
        'MDP': 'Main Distribution Panel',
        'SDP': 'Sub Distribution Panel',
        'LP': 'Lighting Panel',
        'PP': 'Power Panel',
        'CP': 'Control Panel'
    }

    def __init__(self, panel_id: str, nombre: str, tipo: str, ubicacion: str,
                 voltaje_nominal: float = 480, ip: Optional[str] = None):
        self.id = panel_id
        self.nombre = nombre
        self.tipo = tipo
        self.ubicacion = ubicacion
        self.voltaje_nominal = voltaje_nominal
        self.ip = ip
        self.protocolo = "BACnet/IP" if ip else "desconocido"

        self.history = []
        self.last_data = None
        self.alarmas_activas = []
        self.ultimo_mantenimiento = None

        devices_logger.info(f"Panel {self.id} ({self.tipo}) inicializado en {self.ubicacion}")

    def update(self, data: PanelData):
        self.last_data = data
        self.history.append(data)

        if len(self.history) > 1000:
            self.history = self.history[-1000:]

        self._check_alarms(data)

        devices_logger.debug(f"Panel {self.id} actualizado: {data.power_kw:.1f} kW")

    def _check_alarms(self, data: PanelData):
        corrientes = [data.current_l1, data.current_l2, data.current_l3]
        if all(c > 0 for c in corrientes):
            max_c = max(corrientes)
            min_c = min(corrientes)
            if max_c > 0 and ((max_c - min_c) / max_c) > 0.15:
                self._add_alarm('DESBALANCE', f'Desbalance entre fases: {max_c:.0f}A vs {min_c:.0f}A', 'media')

        if data.power_factor and data.power_factor < 0.85:
            self._add_alarm('BAJO_FP', f'Factor potencia bajo: {data.power_factor:.2f}', 'media')

        voltajes = [data.voltage_l1, data.voltage_l2, data.voltage_l3]
        for i, voltaje in enumerate(voltajes):
            if voltaje and (voltaje < self.voltaje_nominal * 0.9 or voltaje > self.voltaje_nominal * 1.1):
                self._add_alarm('VOLTAJE', f'Voltaje fase {i + 1} fuera de rango: {voltaje:.0f}V', 'alta')

        if data.frequency and abs(data.frequency - 60) > 0.5:
            self._add_alarm('FRECUENCIA', f'Frecuencia anómala: {data.frequency:.1f}Hz', 'alta')

        if data.breaker_status != 1:
            estados = {0: 'OFF', 2: 'TRIPPED'}
            self._add_alarm('BREAKER', f'Breaker en estado: {estados.get(data.breaker_status, "DESCONOCIDO")}', 'critica')

    def _add_alarm(self, codigo: str, mensaje: str, severidad: str):
        ahora = datetime.now()

        for alarma in self.alarmas_activas:
            if alarma['codigo'] == codigo and (ahora - alarma['timestamp']).seconds < 3600:
                return

        alarma = {
            'codigo': codigo,
            'mensaje': mensaje,
            'severidad': severidad,
            'timestamp': ahora
        }

        self.alarmas_activas.append(alarma)
        devices_logger.warning(f"⚠️ Panel {self.id}: {mensaje}")

    def clear_alarm(self, codigo: Optional[str] = None):
        if codigo:
            self.alarmas_activas = [a for a in self.alarmas_activas if a['codigo'] != codigo]
            devices_logger.info(f"Panel {self.id}: Alarma {codigo} limpiada")
        else:
            self.alarmas_activas = []
            devices_logger.info(f"Panel {self.id}: Todas las alarmas limpiadas")

    def get_status(self) -> Dict:
        if not self.last_data:
            return {"estado": "sin_datos", "id": self.id}

        corrientes = [self.last_data.current_l1, self.last_data.current_l2, self.last_data.current_l3]
        max_c = max(corrientes)
        min_c = min(corrientes)
        desbalance = round(((max_c - min_c) / max_c) * 100, 1) if max_c > 0 else 0

        return {
            "id": self.id,
            "nombre": self.nombre,
            "tipo": self.tipo,
            "ubicacion": self.ubicacion,
            "voltajes": {
                "L1": round(self.last_data.voltage_l1, 1),
                "L2": round(self.last_data.voltage_l2, 1),
                "L3": round(self.last_data.voltage_l3, 1)
            },
            "corrientes": {
                "L1": round(self.last_data.current_l1, 1),
                "L2": round(self.last_data.current_l2, 1),
                "L3": round(self.last_data.current_l3, 1)
            },
            "potencia_kw": round(self.last_data.power_kw, 1),
            "factor_potencia": round(self.last_data.power_factor, 2) if self.last_data.power_factor else None,
            "frecuencia": self.last_data.frequency,
            "desbalance_pct": desbalance,
            "breaker_status": self.last_data.breaker_status,
            "alarm": self.last_data.alarm,
            "alarmas_activas": [a['mensaje'] for a in self.alarmas_activas],
            "timestamp": self.last_data.timestamp.isoformat(),
            "carga_pct": round((self.last_data.power_kw * 1000 / self.voltaje_nominal / 1.732 / 100), 1)
            if self.voltaje_nominal else 0
        }

    def get_consumo_hoy(self) -> float:
        if not self.history:
            return 0

        hoy = datetime.now().date()
        lecturas_hoy = [d for d in self.history if d.timestamp.date() == hoy]

        if not lecturas_hoy:
            return 0

        return round(sum(d.power_kw for d in lecturas_hoy) * (5 / 60), 1)

    def get_estadisticas(self, days: int = 30) -> Dict:
        if len(self.history) < 10:
            return {}

        cutoff = datetime.now() - timedelta(days=days)
        lecturas_recientes = [d for d in self.history if d.timestamp >= cutoff]

        if not lecturas_recientes:
            return {}

        potencias = [d.power_kw for d in lecturas_recientes]
        voltajes_l1 = [d.voltage_l1 for d in lecturas_recientes if d.voltage_l1]

        return {
            "potencia_media_kw": round(float(np.mean(potencias)), 1),
            "potencia_max_kw": round(float(max(potencias)), 1),
            "potencia_min_kw": round(float(min(potencias)), 1),
            "voltaje_medio_l1": round(float(np.mean(voltajes_l1)), 1) if voltajes_l1 else None,
            "horas_operacion": round(len(lecturas_recientes) * 5 / 60, 1),
            "consumo_total_kwh": round(sum(potencias) * (5 / 60), 1)
        }


class PanelManager:
    """Gestor de paneles eléctricos del complejo"""

    def __init__(self):
        self.paneles = {}

    def add_panel(self, panel: ElectricalPanel):
        self.paneles[panel.id] = panel
        devices_logger.info(f"Panel {panel.id} registrado")

    def get_panel(self, panel_id: str) -> Optional[ElectricalPanel]:
        return self.paneles.get(panel_id)

    def get_all_panels(self) -> List[ElectricalPanel]:
        return list(self.paneles.values())

    def get_panels_by_ubicacion(self, ubicacion: str) -> List[ElectricalPanel]:
        return [p for p in self.paneles.values() if p.ubicacion == ubicacion]

    def get_panels_by_tipo(self, tipo: str) -> List[ElectricalPanel]:
        return [p for p in self.paneles.values() if p.tipo == tipo]

    def get_total_consumo(self) -> float:
        total = 0
        for panel in self.paneles.values():
            if panel.last_data:
                total += panel.last_data.power_kw
        return round(total, 1)

    def get_alertas_globales(self) -> List[Dict]:
        alertas = []
        for panel in self.paneles.values():
            for alarma in panel.alarmas_activas:
                alertas.append({
                    'panel_id': panel.id,
                    'nombre': panel.nombre,
                    **alarma
                })
        return sorted(alertas, key=lambda x: x['timestamp'], reverse=True)


def crear_paneles_proyecto() -> PanelManager:
    """Crea los paneles según los planos EE-4"""

    manager = PanelManager()

    manager.add_panel(ElectricalPanel(
        "MDP-A-480",
        "Main Distribution Panel A 480V",
        "MDP",
        "Electrical Room L1 A",
        480,
        "192.168.10.10"
    ))

    manager.add_panel(ElectricalPanel(
        "MDP-A-208",
        "Main Distribution Panel A 208V",
        "MDP",
        "Electrical Room L1 A",
        208,
        "192.168.10.11"
    ))

    for planta in range(3, 8):
        manager.add_panel(ElectricalPanel(
            f"PP-A-L{planta}",
            f"Power Panel A L{planta}",
            "PP",
            f"Floor L{planta} A",
            208,
            f"192.168.10.1{planta}"
        ))

    manager.add_panel(ElectricalPanel(
        "MDP-B",
        "Main Distribution Panel B",
        "MDP",
        "Electrical Room B",
        480,
        "192.168.20.10"
    ))

    manager.add_panel(ElectricalPanel(
        "MDP-C",
        "Main Distribution Panel C",
        "MDP",
        "Electrical Room C",
        480,
        "192.168.30.10"
    ))

    manager.add_panel(ElectricalPanel(
        "LP-LND1",
        "Lighting Panel Landscape 1",
        "LP",
        "Exterior LND1",
        208,
        "192.168.40.10"
    ))

    manager.add_panel(ElectricalPanel(
        "LP-LND2",
        "Lighting Panel Landscape 2",
        "LP",
        "Exterior LND2",
        208,
        "192.168.40.11"
    ))

    manager.add_panel(ElectricalPanel(
        "PP-POOL",
        "Power Panel Pool",
        "PP",
        "Pool Equipment Room",
        480,
        "192.168.50.10"
    ))

    devices_logger.info(f"✅ Creados {len(manager.paneles)} paneles del proyecto")
    return manager


PANELES = crear_paneles_proyecto()
