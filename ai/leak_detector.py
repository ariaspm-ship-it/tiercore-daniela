# ai/leak_detector.py
# Detector avanzado de fugas de agua con patrón de 3 noches

import asyncio
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict
from dataclasses import dataclass
from collections import defaultdict

from core.config import Config
from core.logger import ai_logger
from core.database import db
from devices.villa import Villa


@dataclass
class LeakAlert:
    """Alerta de fuga generada por el detector"""
    room_id: str
    edificio: str
    caudal_medio_lph: float
    ratio_edificio: float
    confianza: float
    recomendacion: str
    timestamp: datetime
    alerta_id: str


class LeakDetector:
    """
    Detector avanzado de fugas con:
    - Caudal nocturno (2am-5am)
    - Comparación con promedio del edificio
    - Patrón de 3 noches consecutivas
    - Alertas en lenguaje hospitality Kempinski
    """

    def __init__(self):
        self.historial_noches = defaultdict(list)
        self.alertas_enviadas = {}
        self.umbral_base = getattr(Config, 'UMBRAL_FUGA_LPH', 2.0)
        self.dias_para_alerta = 3
        self.night_start = 2
        self.night_end = 5

        ai_logger.info(f"🚀 Detector de fugas inicializado (umbral={self.umbral_base} L/h)")

    def _es_horario_nocturno(self, timestamp: datetime) -> bool:
        hora = timestamp.hour
        return hora >= self.night_start and hora <= self.night_end

    def calcular_caudal_nocturno(self, room) -> float:
        if not room.history or len(room.history) < 10:
            return 0.0

        lecturas_nocturnas = []
        cutoff = datetime.now() - timedelta(days=7)

        for lectura in room.history:
            if lectura.timestamp < cutoff:
                continue
            if self._es_horario_nocturno(lectura.timestamp):
                caudal_lph = lectura.water_cold_m3 * 12 * 1000
                lecturas_nocturnas.append(caudal_lph)

        if not lecturas_nocturnas:
            return 0.0

        return float(np.mean(lecturas_nocturnas))

    def comparar_con_edificio(self, room, todas_habitaciones: List) -> float:
        rooms_mismo_edificio = [
            r for r in todas_habitaciones
            if r.edificio == room.edificio and r.id != room.id
        ]

        if not rooms_mismo_edificio:
            return 1.0

        caudales_edificio = []
        for r in rooms_mismo_edificio:
            caudal = self.calcular_caudal_nocturno(r)
            if caudal > 0:
                caudales_edificio.append(caudal)

        if not caudales_edificio:
            return 1.0

        caudal_medio_edificio = float(np.mean(caudales_edificio))
        caudal_room = self.calcular_caudal_nocturno(room)

        if caudal_medio_edificio == 0:
            return 1.0

        return caudal_room / caudal_medio_edificio

    def detectar_patron_fuga(self, room, dias: int = 3) -> Dict:
        if not room.history:
            return {"fuga_detectada": False, "confianza": 0.0, "caudales": []}

        fechas = set()
        cutoff = datetime.now() - timedelta(days=dias)

        for lectura in room.history:
            if lectura.timestamp >= cutoff:
                fechas.add(lectura.timestamp.date())

        caudales_por_dia = []
        for fecha in fechas:
            lecturas_dia = [
                l for l in room.history
                if l.timestamp.date() == fecha and self._es_horario_nocturno(l.timestamp)
            ]

            if lecturas_dia:
                caudal = float(np.mean([l.water_cold_m3 for l in lecturas_dia]) * 12 * 1000)
                caudales_por_dia.append((fecha, caudal))

        caudales_por_dia.sort(key=lambda x: x[0])
        caudales = [c[1] for c in caudales_por_dia]

        if len(caudales) >= dias:
            todos_superan = all(c > self.umbral_base for c in caudales[-dias:])

            if todos_superan:
                desviacion = float(np.std(caudales[-dias:]))
                confianza = min(0.95, 0.5 + (1.0 - desviacion / 5))

                return {
                    "fuga_detectada": True,
                    "confianza": round(confianza, 2),
                    "caudales": [round(c, 1) for c in caudales[-dias:]],
                    "fechas": [str(f) for f, _ in caudales_por_dia[-dias:]]
                }

        return {"fuga_detectada": False, "confianza": 0.0, "caudales": []}

    def _generar_recomendacion(self, room, caudal: float, ratio: float, confianza: float) -> str:
        tipo = "villa" if isinstance(room, Villa) else "apartamento"

        if confianza > 0.8:
            return (
                f"Atención inmediata requerida en {room.id}. Detected possible water leak in {tipo}. "
                f"Caudal nocturno: {caudal:.1f} L/h ({ratio:.1f}x superior al promedio). Inspeccionar fontanería."
            )
        if confianza > 0.6:
            return f"Programar revisión en {room.id}. Consumo nocturno anómalo detectado en {tipo}: {caudal:.1f} L/h."
        return f"Monitorear {room.id}. Patrón de consumo sospechoso pero requiere confirmación."

    def detectar_fugas(self, habitaciones: List) -> List[LeakAlert]:
        alertas = []
        ahora = datetime.now()

        for room in habitaciones:
            caudal = self.calcular_caudal_nocturno(room)
            ratio = self.comparar_con_edificio(room, habitaciones)
            patron = self.detectar_patron_fuga(room, self.dias_para_alerta)

            if patron["fuga_detectada"] and caudal > self.umbral_base:
                confianza_base = patron["confianza"]
                confianza_ratio = min(0.5, ratio / 4)
                confianza = min(0.95, confianza_base + confianza_ratio)

                if room.id in self.alertas_enviadas:
                    tiempo_desde_alerta = (ahora - self.alertas_enviadas[room.id]).total_seconds()
                    if tiempo_desde_alerta < 86400:
                        continue

                alerta_id = f"LEAK-{room.id}-{ahora.strftime('%Y%m%d%H%M')}"
                recomendacion = self._generar_recomendacion(room, caudal, ratio, confianza)

                alerta = LeakAlert(
                    room_id=room.id,
                    edificio=room.edificio,
                    caudal_medio_lph=round(caudal, 1),
                    ratio_edificio=round(ratio, 1),
                    confianza=confianza,
                    recomendacion=recomendacion,
                    timestamp=ahora,
                    alerta_id=alerta_id
                )

                alertas.append(alerta)
                self.alertas_enviadas[room.id] = ahora

                ai_logger.warning(
                    f"🚨 FUGA DETECTADA: {room.id} | Caudal:{caudal:.1f}L/h | Confianza:{confianza:.0%}"
                )

                try:
                    db.save_alerta({
                        'alerta_id': alerta_id,
                        'tipo': 'fuga',
                        'severidad': 'alta' if confianza > 0.8 else 'media',
                        'dispositivo_id': room.id,
                        'mensaje': f"Posible fuga en {room.id}",
                        'recomendacion': recomendacion,
                        'datos': {
                            'caudal_lph': round(caudal, 1),
                            'ratio': round(ratio, 1),
                            'confianza': confianza
                        },
                        'timestamp': ahora
                    })
                except Exception as error:
                    ai_logger.error(f"Error guardando alerta en BD: {error}")

        return alertas

    async def monitor_loop(self, habitaciones, interval: int = 300):
        ai_logger.info(f"🔄 Monitor de fugas iniciado (intervalo={interval}s)")

        while True:
            try:
                alertas = self.detectar_fugas(habitaciones)
                if alertas:
                    ai_logger.info(f"📢 {len(alertas)} nuevas alertas de fuga generadas")

                await asyncio.sleep(interval)

            except Exception as error:
                ai_logger.error(f"Error en monitor loop: {error}")
                await asyncio.sleep(60)

    def get_estadisticas(self) -> Dict:
        return {
            'fugas_detectadas_24h': len(self.alertas_enviadas),
            'umbral_lph': self.umbral_base,
            'dias_patron': self.dias_para_alerta,
            'timestamp': datetime.now().isoformat()
        }
