# ai/context_builder.py
# Constructor de contexto REAL para el agente Daniela
# Este módulo alimenta a Claude con datos reales del resort

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

from core.logger import ai_logger
from core.config import Config

try:
    from simulator.resort_simulator import ResortSimulator
    SIMULATOR_AVAILABLE = True
except ImportError:
    SIMULATOR_AVAILABLE = False

try:
    from core.database import db, Alerta, LecturaChiller
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False


class ContextBuilder:
    """
    Construye contexto de datos en tiempo real para el agente Daniela.

    Este módulo es CRÍTICO: determina qué sabe Daniela del resort en cada
    momento. Sin buen contexto, Daniela es solo un chatbot genérico.
    Con buen contexto, es una directora de operaciones con superpoderes.

    Datos que inyecta:
    - Estado global del complejo (viviendas, ocupación, consumos)
    - Estado de cada chiller con indicador de degradación
    - Alertas activas no resueltas de las últimas 24h
    - Fugas detectadas con confianza y caudal
    - Consumo por edificio (electricidad + agua)
    - Producción solar actual
    - Resumen financiero (ahorro potencial diario)
    """

    CACHE_TTL_SECONDS = 30

    def __init__(self):
        self.simulator: Optional[ResortSimulator] = None
        self.last_context: Dict[str, Any] = {}
        self.last_update: Optional[datetime] = None

        if SIMULATOR_AVAILABLE and Config.MODO_SIMULACION:
            try:
                self.simulator = ResortSimulator(persist_to_db=False)
                ai_logger.info("Simulador conectado para contexto")
            except Exception as error:
                ai_logger.warning(f"No se pudo conectar simulador: {error}")

        ai_logger.info("ContextBuilder inicializado")

    def _ensure_and_step_simulator(self) -> None:
        """Asegura que el simulador existe y avanza un paso."""
        if not SIMULATOR_AVAILABLE or not Config.MODO_SIMULACION:
            return

        if not self.simulator:
            try:
                self.simulator = ResortSimulator(persist_to_db=False)
            except Exception as error:
                ai_logger.warning(f"No se pudo reconectar simulador: {error}")
                return

        try:
            self.simulator.step()
        except Exception as error:
            ai_logger.warning(f"Error avanzando simulador: {error}")

    def _get_simulator_context(self) -> Dict[str, Any]:
        """Extrae datos del simulador en formato estructurado para Claude."""
        if not self.simulator:
            return {}

        try:
            status = self.simulator.get_global_status()

            # Estado de chillers con indicador de degradación
            chillers = []
            for ch_data in status.get("chillers", []):
                cop = ch_data.get("cop")
                cop_min = Config.UMBRAL_COP_MINIMO
                degraded = False
                if cop and 0 < cop < cop_min:
                    degraded = True

                chillers.append({
                    "id": ch_data.get("id"),
                    "cop": round(cop, 2) if cop else None,
                    "power_kw": round(ch_data.get("power_kw", 0), 1),
                    "status": "degraded" if degraded else ch_data.get("estado", "unknown"),
                    "degraded": degraded,
                    "cop_minimum_threshold": cop_min,
                })

            # Consumo por edificio
            buildings = {}
            for room in self.simulator.habitaciones:
                ed = room.edificio
                if ed not in buildings:
                    buildings[ed] = {
                        "total_units": 0, "units_with_data": 0,
                        "electricity_kwh": 0, "water_m3": 0,
                        "leaks_active": 0,
                    }
                buildings[ed]["total_units"] += 1
                if room.last_data:
                    buildings[ed]["units_with_data"] += 1
                    buildings[ed]["electricity_kwh"] += room.last_data.electricity_kwh
                    buildings[ed]["water_m3"] += room.last_data.water_cold_m3
                    if room.fuga_activa:
                        buildings[ed]["leaks_active"] += 1

            # Redondear valores por edificio
            for ed in buildings:
                buildings[ed]["electricity_kwh"] = round(buildings[ed]["electricity_kwh"], 1)
                buildings[ed]["water_m3"] = round(buildings[ed]["water_m3"], 2)

            # Villas
            villas_data = {
                "total": len(self.simulator.villas),
                "with_data": sum(1 for v in self.simulator.villas if v.last_data),
            }

            # Solar
            solar_kw = 0
            for inv in self.simulator.inversores:
                if inv.last_data and inv.last_data.power_kw:
                    solar_kw += inv.last_data.power_kw
            solar_kw = round(solar_kw, 1)

            # Totales
            total_elec = sum(b["electricity_kwh"] for b in buildings.values())
            total_water = sum(b["water_m3"] for b in buildings.values())
            total_leaks = sum(b["leaks_active"] for b in buildings.values())
            total_units = sum(b["total_units"] for b in buildings.values())

            # Estimación de ahorro potencial (simplificado)
            # Si hay chillers degradados, calcular extra cost
            extra_cost_daily = 0
            for ch in chillers:
                if ch["degraded"] and ch["cop"] and ch["power_kw"]:
                    # Diferencia entre COP actual y mínimo aceptable
                    cop_diff = cop_min - ch["cop"]
                    if cop_diff > 0:
                        extra_power = ch["power_kw"] * (cop_diff / ch["cop"])
                        extra_cost_daily += extra_power * 24 * 0.25  # $0.25/kWh TCI
            extra_cost_daily = round(extra_cost_daily, 0)

            context = {
                "resort": {
                    "total_units": total_units + villas_data["total"],
                    "total_electricity_kwh": round(total_elec, 1),
                    "total_water_m3": round(total_water, 2),
                    "active_leaks": total_leaks,
                    "solar_production_kw": solar_kw,
                },
                "buildings": buildings,
                "villas": villas_data,
                "chillers": chillers,
                "financial": {
                    "extra_cost_from_degradation_daily_usd": extra_cost_daily,
                    "electricity_rate_usd_kwh": 0.25,
                    "currency": "USD",
                },
            }

            return context

        except Exception as error:
            ai_logger.error(f"Error obteniendo contexto del simulador: {error}")
            return {}

    def _get_alerts_context(self) -> List[Dict[str, Any]]:
        """Obtiene alertas activas de la BD para inyectar en el contexto."""
        if not DB_AVAILABLE:
            return []

        try:
            cutoff = datetime.now() - timedelta(hours=24)
            with db.session_scope() as session:
                rows = (
                    session.query(Alerta)
                    .filter(Alerta.resuelta == False, Alerta.timestamp >= cutoff)
                    .order_by(Alerta.timestamp.desc())
                    .limit(10)
                    .all()
                )
                return [
                    {
                        "type": r.tipo,
                        "severity": r.severidad,
                        "device": r.dispositivo_id,
                        "message": r.mensaje,
                        "recommendation": r.recomendacion,
                        "confidence": (r.datos or {}).get("confianza"),
                        "flow_lph": (r.datos or {}).get("caudal_lph"),
                        "time": r.timestamp.strftime("%H:%M") if r.timestamp else None,
                    }
                    for r in rows
                ]
        except Exception as error:
            ai_logger.error(f"Error obteniendo alertas: {error}")
            return []

    def get_realtime_context(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Construye el contexto completo que se inyecta en cada llamada a Claude.

        Usa caché de 30s para no saturar el simulador/BD.
        """
        if not force_refresh and self.last_update:
            elapsed = (datetime.now() - self.last_update).total_seconds()
            if elapsed < self.CACHE_TTL_SECONDS and self.last_context:
                return self.last_context

        self._ensure_and_step_simulator()

        now = datetime.now()
        context: Dict[str, Any] = {
            "timestamp": now.strftime("%Y-%m-%d %H:%M"),
            "hour": now.hour,
            "property": {
                "name": Config.PROYECTO_NOMBRE,
                "total_units": Config.get_total_viviendas(),
                "brand": "Kempinski",
                "location": "Grace Bay, Turks & Caicos",
            },
        }

        # Datos del simulador (o hardware cuando esté disponible)
        sim_context = self._get_simulator_context()
        if sim_context:
            context.update(sim_context)

        # Alertas activas de la BD
        alerts = self._get_alerts_context()
        if alerts:
            context["active_alerts"] = alerts
            context["alert_summary"] = {
                "total": len(alerts),
                "high": sum(1 for a in alerts if a["severity"] == "alta"),
                "medium": sum(1 for a in alerts if a["severity"] == "media"),
            }

        self.last_context = context
        self.last_update = now

        context_size = len(json.dumps(context, default=str))
        ai_logger.debug(f"Contexto actualizado ({context_size} bytes, "
                        f"{len(alerts)} alertas)")
        return context

    def get_formatted_context(self, max_length: int = 3000) -> str:
        """
        Retorna el contexto como texto legible (para debug o prompt directo).
        """
        context = self.get_realtime_context()

        lines: List[str] = []
        lines.append(f"=== RESORT STATUS — {context.get('timestamp', 'N/A')} ===")
        lines.append(f"Property: {context.get('property', {}).get('name', 'N/A')}")

        resort = context.get("resort", {})
        if resort:
            lines.append(f"Units: {resort.get('total_units', 0)}")
            lines.append(f"Electricity: {resort.get('total_electricity_kwh', 0)} kWh")
            lines.append(f"Water: {resort.get('total_water_m3', 0)} m³")
            lines.append(f"Active leaks: {resort.get('active_leaks', 0)}")
            lines.append(f"Solar: {resort.get('solar_production_kw', 0)} kW")

        chillers = context.get("chillers", [])
        if chillers:
            lines.append("\n--- CHILLERS ---")
            for ch in chillers:
                status = "⚠ DEGRADED" if ch.get("degraded") else ch.get("status", "?")
                cop = ch.get("cop")
                cop_str = f"COP {cop}" if cop else "OFF"
                lines.append(f"  {ch['id']}: {cop_str} | {ch.get('power_kw', 0)} kW | {status}")

        financial = context.get("financial", {})
        if financial.get("extra_cost_from_degradation_daily_usd", 0) > 0:
            lines.append(f"\nExtra cost from chiller degradation: "
                         f"${financial['extra_cost_from_degradation_daily_usd']}/day")

        alerts = context.get("active_alerts", [])
        if alerts:
            lines.append(f"\n--- ACTIVE ALERTS ({len(alerts)}) ---")
            for a in alerts[:5]:
                lines.append(f"  [{a['severity'].upper()}] {a['device']}: {a['message']}")

        result = "\n".join(lines)
        if len(result) > max_length:
            result = result[:max_length] + "\n... [truncated]"
        return result

    def get_alertas_recientes(self, horas: int = 24) -> List[Dict[str, Any]]:
        """Alertas recientes — usado por API y dashboard."""
        return self._get_alerts_context()

    def get_consumption_by_building(self) -> Dict[str, Dict[str, float]]:
        """Consumo actual por edificio — usado por API."""
        context = self.get_realtime_context()
        return context.get("buildings", {})


# Singleton
_context_builder: Optional[ContextBuilder] = None


def get_context_builder() -> ContextBuilder:
    global _context_builder
    if _context_builder is None:
        _context_builder = ContextBuilder()
    return _context_builder


if __name__ == "__main__":
    cb = ContextBuilder()
    ctx = cb.get_realtime_context()
    print(json.dumps(ctx, indent=2, default=str))
    print("\n" + "=" * 60)
    print(cb.get_formatted_context())
