#!/usr/bin/env python3
# DANIELA v0.3 — Orquestador principal
#
# Levanta TODOS los sistemas:
# 1. Simulador (o hardware cuando esté disponible)
# 2. Detector de fugas (cada 12 pasos = ~1h simulada)
# 3. Optimizador de chillers (cada 12 pasos)
# 4. API FastAPI en puerto 8000 (thread separado)
#
# Uso:
#   python main.py                        # 288 pasos, con API
#   python main.py --steps 100 --no-api   # solo simulación
#   python main.py --continuous            # corre indefinidamente

import argparse
import asyncio
import threading
from datetime import datetime

from core.logger import main_logger
from core.config import Config
from simulator.resort_simulator import ResortSimulator
from ai.leak_detector import LeakDetector
from ai.chiller_optimizer import ChillerOptimizer


def start_api_server(host: str = "0.0.0.0", port: int = 8000):
    """Inicia el servidor FastAPI en un thread separado."""
    try:
        import uvicorn
        from backend.main import app
        main_logger.info(f"Iniciando API server en {host}:{port}")
        uvicorn.run(app, host=host, port=port, log_level="warning")
    except ImportError:
        main_logger.warning("uvicorn o fastapi no disponible — API no iniciada")
    except Exception as error:
        main_logger.error(f"Error iniciando API: {error}")


async def run_orchestrator(
    steps: int,
    interval_seconds: float,
    continuous: bool = False,
    start_api: bool = True,
):
    """
    Bucle principal del orquestador.

    Ejecuta el simulador paso a paso, y cada 12 pasos (~1h simulada):
    - Corre el detector de fugas sobre todas las habitaciones + villas
    - Corre el optimizador de chillers
    - Guarda alertas en la base de datos
    """
    main_logger.info("=" * 60)
    main_logger.info("DANIELA v0.3 — Orquestador principal")
    main_logger.info("=" * 60)

    # Inicializar sistemas
    simulator = ResortSimulator(persist_to_db=True)
    leak_detector = LeakDetector()
    chiller_optimizer = ChillerOptimizer()

    main_logger.info(f"Simulador: {len(simulator.habitaciones)} habitaciones, "
                     f"{len(simulator.villas)} villas, "
                     f"{len(simulator.chillers)} chillers")
    main_logger.info(f"Modo: {'continuo' if continuous else f'{steps} pasos'}")
    main_logger.info(f"Intervalo: {interval_seconds}s entre pasos")
    main_logger.info(f"API: {'activada' if start_api else 'desactivada'}")

    # Arrancar API en thread separado
    if start_api:
        api_thread = threading.Thread(
            target=start_api_server,
            kwargs={"host": "0.0.0.0", "port": 8000},
            daemon=True,
        )
        api_thread.start()
        main_logger.info("API thread iniciado en :8000")

    main_logger.info("=" * 60)
    main_logger.info("Simulación en marcha")
    main_logger.info("=" * 60)

    index = 0
    try:
        while continuous or index < steps:
            # Avanzar simulación
            simulator.step()

            # Cada 12 pasos (~1h simulada) correr análisis
            if index % 12 == 0 and index > 0:
                # Detección de fugas
                all_rooms = simulator.habitaciones + simulator.villas
                alertas_fuga = leak_detector.detectar_fugas(all_rooms)
                if alertas_fuga:
                    main_logger.warning(
                        f"Paso {index}: {len(alertas_fuga)} alertas de fuga"
                    )

                # Optimización de chillers
                resultados = chiller_optimizer.optimizar(
                    simulator.chillers,
                    temp_exterior=28,
                    ocupacion=1.0
                )
                degradados = [r for r in resultados if "degradación" in r.recomendacion.lower()]
                if degradados:
                    main_logger.warning(
                        f"Paso {index}: {len(degradados)} chillers con degradación"
                    )

            # Log de progreso cada 100 pasos
            if index % 100 == 0:
                status = simulator.get_global_status()
                main_logger.info(
                    f"Paso {index}"
                    f"{'/' + str(steps) if not continuous else ''} | "
                    f"Elec={status['consumos']['electricidad_kwh']} kWh | "
                    f"Agua={status['consumos']['agua_m3']} m³ | "
                    f"Fugas={status['habitaciones']['fugas_activas']}"
                )

            index += 1
            await asyncio.sleep(interval_seconds)

    except KeyboardInterrupt:
        main_logger.info("Interrupción por usuario")
    finally:
        final = simulator.get_global_status()
        main_logger.info("=" * 60)
        main_logger.info("Orquestador finalizado")
        main_logger.info(f"Pasos ejecutados: {index}")
        main_logger.info(f"Lecturas totales: {final['stats']['total_lecturas']}")
        main_logger.info(f"Fugas detectadas: {final['stats']['fugas_detectadas']}")
        main_logger.info("=" * 60)


def parse_args():
    parser = argparse.ArgumentParser(description="DANIELA v0.3 Orquestador")
    parser.add_argument(
        "--steps", type=int, default=288,
        help="Pasos de simulación (default: 288 = 24h simuladas)"
    )
    parser.add_argument(
        "--interval", type=float, default=0.05,
        help="Espera real entre pasos en segundos"
    )
    parser.add_argument(
        "--continuous", action="store_true",
        help="Correr indefinidamente"
    )
    parser.add_argument(
        "--no-api", action="store_true",
        help="No arrancar el servidor API"
    )
    parser.add_argument(
        "--api-port", type=int, default=8000,
        help="Puerto del servidor API"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main_logger.info(f"Inicio: {datetime.now().isoformat()}")
    asyncio.run(
        run_orchestrator(
            steps=args.steps,
            interval_seconds=args.interval,
            continuous=args.continuous,
            start_api=not args.no_api,
        )
    )
