#!/usr/bin/env python3
# DANIELA v0.2 - Orquestador principal

import argparse
import asyncio
from datetime import datetime

from core.logger import main_logger
from simulator.resort_simulator import ResortSimulator
from ai.leak_detector import LeakDetector
from ai.chiller_optimizer import ChillerOptimizer


async def run_orchestrator(steps: int, interval_seconds: float):
    main_logger.info("Iniciando orquestador DANIELA v0.2")

    simulator = ResortSimulator(persist_to_db=True)
    leak_detector = LeakDetector()
    chiller_optimizer = ChillerOptimizer()

    for index in range(steps):
        simulator.step()

        if index % 12 == 0:
            alertas = leak_detector.detectar_fugas(simulator.habitaciones + simulator.villas)
            if alertas:
                main_logger.warning(f"Alertas de fuga generadas: {len(alertas)}")

        if index % 12 == 0:
            resultados = chiller_optimizer.optimizar(simulator.chillers, temp_exterior=28, ocupacion=1.0)
            main_logger.info(f"Optimizacion de chillers ejecutada: {len(resultados)} resultados")

        if index % 100 == 0:
            status = simulator.get_global_status()
            main_logger.info(
                f"Paso {index}/{steps} | "
                f"Elec={status['consumos']['electricidad_kwh']} kWh | "
                f"Agua={status['consumos']['agua_m3']} m3"
            )

        await asyncio.sleep(interval_seconds)

    main_logger.info("Orquestador finalizado")
    final_status = simulator.get_global_status()
    main_logger.info(f"Estado final: {final_status['timestamp']}")


def parse_args():
    parser = argparse.ArgumentParser(description="DANIELA v0.2 Orquestador")
    parser.add_argument("--steps", type=int, default=288, help="Pasos de simulación (default: 288)")
    parser.add_argument("--interval", type=float, default=0.05, help="Espera real entre pasos en segundos")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main_logger.info(f"Inicio: {datetime.now().isoformat()}")
    asyncio.run(run_orchestrator(args.steps, args.interval))
