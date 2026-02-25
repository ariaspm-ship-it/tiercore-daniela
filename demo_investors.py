import asyncio
import logging
import time
from datetime import datetime
from typing import Any


def print_slow(text: str, delay: float = 0.008) -> None:
    for char in text:
        print(char, end="", flush=True)
        time.sleep(delay)
    print()


def print_header() -> None:
    print("=" * 72)


def quiet_project_logs() -> None:
    logging.disable(logging.CRITICAL)
    for logger_name in ["daniela", "devices", "simulator", "ai", "protocols"]:
        logging.getLogger(logger_name).setLevel(logging.ERROR)
    print("DANIELA - DEMO PARA INVERSORES")
    print("=" * 72)


async def build_simulated_state(steps: int = 36) -> Any:
    from simulator.resort_simulator import ResortSimulator

    simulator = ResortSimulator(persist_to_db=False)
    await simulator.run(steps=steps)
    return simulator


def show_dashboard(simulator: Any) -> None:
    status = simulator.get_global_status()
    total_units = status["habitaciones"]["total"] + status["villas"]["total"]

    print("\n" + "-" * 72)
    print("ESCENA 1 - VISTA GENERAL")
    print("-" * 72)
    print(f"Fecha/hora: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"Viviendas monitorizadas: {total_units}")
    print(f"Puntos lógicos aproximados: {status.get('total_puntos_logicos', 0)}")
    print(f"Consumo eléctrico hoy: {status['consumos']['electricidad_kwh']} kWh")
    print(f"Consumo de agua hoy: {status['consumos']['agua_m3']} m3")
    print(f"Fugas activas: {status['habitaciones']['fugas_activas']}")

    print("\nEstado de chillers:")
    for chiller in status["chillers"]:
        print(
            f"- {chiller['id']}: COP={chiller.get('cop')} | Potencia={chiller.get('power_kw')} kW | Estado={chiller.get('estado')}"
        )


def run_chiller_optimization(simulator: Any) -> None:
    from ai.chiller_optimizer import ChillerOptimizer

    optimizer = ChillerOptimizer()
    results = optimizer.optimizar(simulator.chillers, temp_exterior=28)
    total_saving = sum(result.ahorro_potencial_euro_dia for result in results)

    print("\n" + "-" * 72)
    print("ESCENA 2 - OPTIMIZACION DE CHILLERS")
    print("-" * 72)
    for result in results:
        print(
            f"- {result.chiller_id}: COP {result.cop_actual:.2f} | Objetivo {result.cop_objetivo:.2f} | "
            f"Ahorro potencial {result.ahorro_potencial_euro_dia:.1f} EUR/dia"
        )
        print(f"  Recomendacion: {result.recomendacion}")

    print(f"\nAhorro potencial agregado: {total_saving:.1f} EUR/dia")


def run_leak_detection(simulator: Any) -> None:
    from ai.leak_detector import LeakDetector

    detector = LeakDetector()
    alerts = detector.detectar_fugas(simulator.habitaciones)

    print("\n" + "-" * 72)
    print("ESCENA 3 - DETECCION DE FUGAS")
    print("-" * 72)

    if not alerts:
        print("No se detectaron fugas confirmadas con patron de 3 noches en esta corrida rapida.")
        active_leaks = [room for room in simulator.habitaciones if getattr(room, "fuga_activa", False)]
        print(f"Indicadores de fuga activa en simulacion actual: {len(active_leaks)}")
        return

    for alert in alerts[:3]:
        print(
            f"- {alert.room_id} ({alert.edificio}): {alert.caudal_medio_lph} L/h | "
            f"Confianza {alert.confianza:.0%}"
        )
        print(f"  Recomendacion: {alert.recomendacion}")

    print(f"\nTotal alertas generadas: {len(alerts)}")


def run_conversational_demo() -> None:
    from ai.claude_agent import DanielaAgent

    agent = DanielaAgent()
    queries = [
        "Como estan los chillers hoy?",
        "Hay alguna fuga de agua?",
        "Cuanto podemos ahorrar este mes?",
    ]

    print("\n" + "-" * 72)
    print("ESCENA 4 - AGENTE CONVERSACIONAL")
    print("-" * 72)
    for query in queries:
        print(f"\nTu: {query}")
        answer = agent.chat(query)
        print(f"Daniela: {answer}")


def show_projection() -> None:
    print("\n" + "-" * 72)
    print("ESCENA 5 - PROYECCION A DATA CENTERS")
    print("-" * 72)
    print("Metricas actuales (resort):")
    print("- 191 viviendas | ~2.100 puntos | 3 chillers")
    print("- Ahorro anual estimado: 190.000 EUR | ROI < 6 meses")
    print("\nProyeccion data center T2 (5MW):")
    print("- Puntos equivalentes: ~8.000")
    print("- Ahorro anual estimado: 850.000 EUR")
    print("- ROI estimado: < 8 meses")


def demo() -> None:
    quiet_project_logs()
    print_header()
    print_slow("Inicializando simulacion y motor de IA...")

    simulator = asyncio.run(build_simulated_state())
    show_dashboard(simulator)
    run_chiller_optimization(simulator)
    run_leak_detection(simulator)
    run_conversational_demo()
    show_projection()

    print("\n" + "=" * 72)
    print("CIERRE")
    print("Buscamos 150.000 EUR para completar hito Q2 2026 y escalar piloto.")
    print("=" * 72)


if __name__ == "__main__":
    demo()
