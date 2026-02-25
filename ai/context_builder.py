# ai/context_builder.py
# Constructor de contexto para el agente Daniela

from typing import Dict, List, Any
from datetime import datetime
import json

from core.logger import ai_logger
from core.config import Config

try:
    from simulator.resort_simulator import ResortSimulator
    SIMULATOR_AVAILABLE = True
except ImportError:
    SIMULATOR_AVAILABLE = False

try:
    from core.database import db  # noqa: F401
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False


class ContextBuilder:
    """
    Construye contexto de datos en tiempo real para el agente Daniela.
    """

    def __init__(self):
        self.simulator = None
        self.last_context: Dict[str, Any] = {}
        self.last_update = None

        if SIMULATOR_AVAILABLE and Config.MODO_SIMULACION:
            try:
                self.simulator = ResortSimulator(persist_to_db=False)
                ai_logger.info("Simulador conectado para contexto")
            except Exception as error:
                ai_logger.warning(f"No se pudo conectar simulador para contexto: {error}")

        ai_logger.info("ContextBuilder inicializado")

    def _get_simulator_context(self) -> Dict[str, Any]:
        if not self.simulator:
            return {}

        try:
            status = self.simulator.get_global_status()

            context = {
                "timestamp": status.get("timestamp"),
                "resumen": {
                    "habitaciones_totales": status.get("habitaciones", {}).get("total", 0),
                    "fugas_activas": status.get("habitaciones", {}).get("fugas_activas", 0),
                    "consumo_electrico_kwh": status.get("consumos", {}).get("electricidad_kwh", 0),
                    "consumo_agua_m3": status.get("consumos", {}).get("agua_m3", 0)
                },
                "chillers": []
            }

            for chiller in status.get("chillers", []):
                if chiller.get("power_kw", 0) > 0:
                    context["chillers"].append({
                        "id": chiller.get("id"),
                        "cop": chiller.get("cop"),
                        "potencia_kw": chiller.get("power_kw"),
                        "estado": chiller.get("estado")
                    })

            return context

        except Exception as error:
            ai_logger.error(f"Error obteniendo contexto del simulador: {error}")
            return {}

    def _get_database_context(self) -> Dict[str, Any]:
        if not DB_AVAILABLE:
            return {}

        return {
            "nota": "Integración con base de datos histórica pendiente",
            "fase": "2"
        }

    def get_realtime_context(self, force_refresh: bool = False) -> Dict[str, Any]:
        if not force_refresh and self.last_update:
            elapsed = (datetime.now() - self.last_update).total_seconds()
            if elapsed < 30 and self.last_context:
                return self.last_context

        context: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "complejo": {
                "nombre": Config.PROYECTO_NOMBRE,
                "total_viviendas": Config.get_total_viviendas(),
                "edificios": Config.EDIFICIOS
            }
        }

        sim_context = self._get_simulator_context()
        if sim_context:
            context["tiempo_real"] = sim_context

        db_context = self._get_database_context()
        if db_context:
            context["historico"] = db_context

        self.last_context = context
        self.last_update = datetime.now()

        ai_logger.debug(f"Contexto actualizado ({len(json.dumps(context, default=str))} chars)")
        return context

    def get_formatted_context(self, max_length: int = 2000) -> str:
        context = self.get_realtime_context()

        lines: List[str] = []
        lines.append("=== CONTEXTO DEL RESORT ===")
        lines.append(f"Fecha: {context.get('timestamp', 'N/A')}")
        lines.append(f"Complejo: {context.get('complejo', {}).get('nombre', 'N/A')}")
        lines.append(f"Viviendas: {context.get('complejo', {}).get('total_viviendas', 0)}")

        if "tiempo_real" in context:
            tr = context["tiempo_real"]
            lines.append("\n--- TIEMPO REAL ---")
            lines.append(f"Consumo eléctrico: {tr.get('resumen', {}).get('consumo_electrico_kwh', 0)} kWh")
            lines.append(f"Consumo agua: {tr.get('resumen', {}).get('consumo_agua_m3', 0)} m3")
            lines.append(f"Fugas activas: {tr.get('resumen', {}).get('fugas_activas', 0)}")

            if tr.get("chillers"):
                lines.append("\nChillers activos:")
                for chiller in tr["chillers"]:
                    lines.append(f"  - {chiller.get('id')}: COP {chiller.get('cop', 0)}")

        result = "\n".join(lines)
        if len(result) > max_length:
            result = result[:max_length] + "... [contexto truncado]"
        return result

    def get_alertas_recientes(self, horas: int = 24) -> List[Dict[str, Any]]:
        return []

    def get_top_consumidores(self, limite: int = 5) -> List[Dict[str, Any]]:
        return []


_context_builder = None


def get_context_builder() -> ContextBuilder:
    global _context_builder
    if _context_builder is None:
        _context_builder = ContextBuilder()
    return _context_builder


if __name__ == "__main__":
    cb = ContextBuilder()
    print(json.dumps(cb.get_realtime_context(), indent=2, default=str))
    print("\n" + "=" * 60)
    print(cb.get_formatted_context())
