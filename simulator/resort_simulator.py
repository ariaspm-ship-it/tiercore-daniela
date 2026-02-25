# simulator/resort_simulator.py
# Simulador completo del resort (191 viviendas, chillers, etc.) - VERSIÓN COMPLETA

import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, Optional

from core.logger import simulator_logger
from core.database import db
from devices.chiller import Chiller, ChillerData
from devices.villa import Villa, VillaData
from devices.heat_machine import HeatMachine, HeatMachineData
from devices.inverter import Inverter, InverterData
from devices.panel import ElectricalPanel, PanelData, crear_paneles_proyecto

from generators.habitaciones import generar_habitaciones
from generators.villas import generar_villas
from generators.edificios import crear_edificios


class ResortSimulator:
    """
    Simulador completo del resort
    Genera datos realistas para todas las viviendas y equipos
    Versión completa con todos los puntos BMS (~2.100 puntos lógicos)
    """

    def __init__(self, persist_to_db: bool = True):
        self.habitaciones = generar_habitaciones()
        self.villas = generar_villas()
        self.edificios = crear_edificios()
        self.paneles = crear_paneles_proyecto()
        self.persist_to_db = persist_to_db

        if self.persist_to_db:
            db.create_tables()

        self.timestamp = datetime.now()
        self.running = False
        self.step_interval = 5
        self.real_time_step = 0.1

        self.chillers = [
            Chiller("2CH-1", "Chiller RTAG-01", "192.168.10.10"),
            Chiller("2CH-2", "Chiller RTAG-02", "192.168.10.11"),
            Chiller("2CH-3", "Chiller RTAG-03", "192.168.10.12")
        ]

        self.heat_machines = [
            HeatMachine("CXAU-1", "Heat Machine 1", "192.168.10.20"),
            HeatMachine("CXAU-2", "Heat Machine 2", "192.168.10.21")
        ]

        self.inversores = [
            Inverter("INV-A1", "Solar A1", "Roof Building A"),
            Inverter("INV-A2", "Solar A2", "Roof Building A"),
            Inverter("INV-C1", "Solar C1", "Roof Building C"),
            Inverter("INV-C2", "Solar C2", "Roof Building C"),
            Inverter("INV-C3", "Solar C3", "Roof Building C")
        ]

        self.all_devices = (
            self.habitaciones +
            self.villas +
            self.chillers +
            self.heat_machines +
            self.inversores +
            self.paneles.get_all_panels()
        )

        self.stats = {
            "total_lecturas": 0,
            "fugas_detectadas": 0,
            "alertas_generadas": 0,
            "total_puntos_logicos": len(self.all_devices) * 5
        }

        simulator_logger.info("=" * 60)
        simulator_logger.info("🚀 SIMULADOR DEL RESORT INICIALIZADO")
        simulator_logger.info("=" * 60)
        simulator_logger.info(f"🏢 {len(self.habitaciones)} habitaciones")
        simulator_logger.info(f"🏡 {len(self.villas)} villas")
        simulator_logger.info(f"❄️ {len(self.chillers)} chillers")
        simulator_logger.info(f"🔥 {len(self.heat_machines)} heat machines")
        simulator_logger.info(f"☀️ {len(self.inversores)} inversores")
        simulator_logger.info(f"⚡ {len(self.paneles.get_all_panels())} paneles eléctricos")
        simulator_logger.info(f"📊 Total puntos lógicos: ~{self.stats['total_puntos_logicos']}")
        simulator_logger.info("=" * 60)

    def generar_lectura_habitacion(self, room):
        hora = self.timestamp.hour
        dia_semana = self.timestamp.weekday()

        if 0 <= hora < 6:
            factor_elec = random.uniform(0.1, 0.3)
            factor_agua = random.uniform(0, 0.1)
        elif 7 <= hora < 10:
            factor_elec = random.uniform(0.3, 0.6)
            factor_agua = random.uniform(0.4, 1.2)
        elif 18 <= hora < 23:
            factor_elec = random.uniform(0.5, 1.0)
            factor_agua = random.uniform(0.3, 0.8)
        else:
            factor_elec = random.uniform(0.2, 0.4)
            factor_agua = random.uniform(0.1, 0.3)

        if dia_semana >= 5:
            factor_elec *= 1.2
            factor_agua *= 1.3

        factor_elec *= random.uniform(0.8, 1.2)
        factor_agua *= random.uniform(0.8, 1.2)

        fuga = random.random() < 0.005
        if fuga:
            factor_agua *= random.uniform(3, 8)
            self.stats["fugas_detectadas"] += 1

        from devices.room import RoomData
        return RoomData(
            timestamp=self.timestamp,
            electricity_kwh=round(factor_elec, 2),
            water_cold_m3=round(factor_agua, 2),
            water_hot_m3=round(factor_agua * 0.35, 2),
            fc_kwh=round(factor_elec * 1.8, 2),
            return_temp=round(45 + random.uniform(-3, 3), 1),
            fuga_detectada=fuga
        )

    def generar_lectura_villa(self, villa: Villa) -> VillaData:
        hora = self.timestamp.hour
        mes = self.timestamp.month

        factor_elec = random.uniform(1.5, 3.0)
        factor_agua = random.uniform(0.5, 1.5)

        if 10 <= hora <= 20 and mes in [4, 5, 6, 7, 8, 9, 10]:
            pool_kwh = random.uniform(2.0, 4.0)
        else:
            pool_kwh = 0

        if hora in [6, 7, 8, 18, 19, 20]:
            riego_m3 = random.uniform(0.3, 0.8)
        else:
            riego_m3 = 0

        factor_elec *= random.uniform(0.9, 1.1)
        factor_agua *= random.uniform(0.9, 1.1)

        return VillaData(
            timestamp=self.timestamp,
            electricity_kwh=round(factor_elec + pool_kwh, 2),
            water_cold_m3=round(factor_agua, 2),
            water_hot_m3=round(factor_agua * 0.4, 2),
            pool_kwh=round(pool_kwh, 2),
            irrigation_m3=round(riego_m3, 2),
            fuga_detectada=random.random() < 0.002
        )

    def generar_lectura_chiller(self, chiller: Chiller, idx: int) -> ChillerData:
        hora = self.timestamp.hour

        if 12 <= hora < 16:
            demanda = 450 + random.uniform(-30, 30)
        elif 0 <= hora < 6:
            demanda = 180 + random.uniform(-20, 20)
        else:
            demanda = 280 + random.uniform(-40, 40)

        if chiller.id == "2CH-3":
            if random.random() < 0.3:
                return ChillerData(
                    timestamp=self.timestamp,
                    temp_supply=None,
                    temp_return=None,
                    power_kw=0,
                    cooling_kw=0,
                    cop=None,
                    compressor_status=0,
                    alarm=False,
                    flow_m3h=0
                )

        cop_objetivo = 3.8 + random.uniform(-0.2, 0.4)
        power = round(demanda / cop_objetivo, 1)
        flow = round(demanda / (5 * 1.16), 1)

        return ChillerData(
            timestamp=self.timestamp,
            temp_supply=round(7 + random.uniform(-0.5, 0.5), 1),
            temp_return=round(12 + random.uniform(-0.5, 0.5), 1),
            power_kw=power,
            cooling_kw=round(demanda, 1),
            cop=round(cop_objetivo, 2),
            compressor_status=random.randint(1, 3),
            alarm=random.random() < 0.01,
            flow_m3h=flow
        )

    def generar_lectura_heat_machine(self, hm: HeatMachine, idx: int) -> HeatMachineData:
        hora = self.timestamp.hour

        if 7 <= hora < 10 or 19 <= hora < 22:
            demanda = 80 + random.uniform(-10, 10)
        else:
            demanda = 30 + random.uniform(-5, 15)

        efficiency = 3.2 + random.uniform(-0.2, 0.3)
        power = round(demanda / efficiency, 1)

        return HeatMachineData(
            timestamp=self.timestamp,
            temp_supply=round(58 + random.uniform(-2, 2), 1),
            temp_return=round(48 + random.uniform(-2, 2), 1),
            power_kw=power,
            heating_kw=round(demanda, 1),
            efficiency=round(efficiency, 2),
            pump_status=random.randint(0, 2),
            alarm=random.random() < 0.005
        )

    def generar_lectura_inversor(self, inv: Inverter, idx: int) -> InverterData:
        hora = self.timestamp.hour
        mes = self.timestamp.month

        if 7 <= hora <= 18:
            if 11 <= hora <= 14:
                potencia = 15 + random.uniform(-2, 5)
            elif 9 <= hora <= 16:
                potencia = 10 + random.uniform(-3, 4)
            else:
                potencia = 3 + random.uniform(-1, 2)

            if mes in [6, 7, 8]:
                potencia *= 1.2
            elif mes in [12, 1, 2]:
                potencia *= 0.6
        else:
            potencia = 0

        return InverterData(
            timestamp=self.timestamp,
            power_kw=round(potencia, 1),
            voltage=round(400 + random.uniform(-10, 10), 1),
            current=round(potencia * 2.5, 1),
            grid_power_kw=round(potencia * 0.95, 1),
            temperature=round(35 + random.uniform(-5, 15), 1),
            efficiency=round(95 + random.uniform(-2, 3), 1),
            status="Funcionando" if potencia > 0.5 else "Standby"
        )

    def generar_lectura_panel(self, panel: ElectricalPanel) -> Optional[PanelData]:
        if not panel.last_data:
            base_power = 100 + random.uniform(-20, 20)
        else:
            base_power = panel.last_data.power_kw * random.uniform(0.95, 1.05)

        hora = self.timestamp.hour
        if 18 <= hora <= 22:
            base_power *= 1.2
        elif 0 <= hora <= 5:
            base_power *= 0.6

        voltaje_base = 480 if '480' in panel.id else 208
        corriente = base_power * 1000 / voltaje_base / 1.732 if base_power > 0 else 0

        return PanelData(
            timestamp=self.timestamp,
            voltage_l1=voltaje_base * random.uniform(0.98, 1.02),
            voltage_l2=voltaje_base * random.uniform(0.98, 1.02),
            voltage_l3=voltaje_base * random.uniform(0.98, 1.02),
            current_l1=corriente * random.uniform(0.95, 1.05),
            current_l2=corriente * random.uniform(0.95, 1.05),
            current_l3=corriente * random.uniform(0.95, 1.05),
            power_kw=base_power,
            power_factor=random.uniform(0.92, 0.99),
            frequency=60 + random.uniform(-0.1, 0.1),
            alarm=random.random() < 0.01,
            breaker_status=1 if random.random() > 0.01 else 0
        )

    def step(self):
        self.timestamp += timedelta(minutes=self.step_interval)

        for room in self.habitaciones:
            data = self.generar_lectura_habitacion(room)
            room.update(data)
            if self.persist_to_db:
                db.save_lectura_habitacion(room.id, room.edificio, data)

        for villa in self.villas:
            data = self.generar_lectura_villa(villa)
            villa.update(data)
            if self.persist_to_db:
                db.save_lectura_habitacion(villa.id, villa.edificio, data)

        for i, chiller in enumerate(self.chillers):
            data = self.generar_lectura_chiller(chiller, i)
            chiller.update(data)
            if self.persist_to_db:
                db.save_lectura_chiller(chiller.id, data)

        for i, hm in enumerate(self.heat_machines):
            data = self.generar_lectura_heat_machine(hm, i)
            hm.update(data)

        for i, inv in enumerate(self.inversores):
            data = self.generar_lectura_inversor(inv, i)
            inv.update(data)

        for panel in self.paneles.get_all_panels():
            data = self.generar_lectura_panel(panel)
            if data:
                panel.update(data)
                if self.persist_to_db:
                    db.save_lectura_panel(panel.id, data)

        self.stats["total_lecturas"] += len(self.all_devices)

        if self.stats["total_lecturas"] % 10000 == 0:
            simulator_logger.info(f"📊 Progreso: {self.stats['total_lecturas']} lecturas generadas")

    async def run(self, steps: Optional[int] = None):
        self.running = True
        self.timestamp = datetime.now()

        simulator_logger.info("🚀 Simulación iniciada")

        try:
            if steps:
                for i in range(steps):
                    self.step()
                    if (i + 1) % 100 == 0:
                        simulator_logger.info(f"Paso {i + 1}/{steps} completado")
                    await asyncio.sleep(0.01)
            else:
                while self.running:
                    self.step()
                    await asyncio.sleep(self.real_time_step)
        except KeyboardInterrupt:
            self.stop()
        except Exception as error:
            simulator_logger.error(f"Error en simulación: {error}")
        finally:
            self.stop()

    def stop(self):
        self.running = False
        simulator_logger.info("⏹️ Simulación detenida")
        simulator_logger.info(f"📊 Estadísticas finales: {self.stats}")

    def get_global_status(self) -> Dict:
        total_elec = sum(r.last_data.electricity_kwh for r in self.habitaciones if r.last_data)
        total_agua = sum(r.last_data.water_cold_m3 for r in self.habitaciones if r.last_data)
        fugas = sum(1 for r in self.habitaciones if hasattr(r, 'fuga_activa') and r.fuga_activa)

        return {
            "timestamp": self.timestamp.isoformat(),
            "habitaciones": {
                "total": len(self.habitaciones),
                "con_datos": sum(1 for r in self.habitaciones if r.last_data),
                "fugas_activas": fugas
            },
            "villas": {
                "total": len(self.villas),
                "con_datos": sum(1 for v in self.villas if v.last_data)
            },
            "consumos": {
                "electricidad_kwh": round(total_elec, 1),
                "agua_m3": round(total_agua, 1)
            },
            "chillers": [c.get_status() for c in self.chillers],
            "stats": self.stats,
            "total_puntos_logicos": self.stats['total_puntos_logicos']
        }


async def main():
    sim = ResortSimulator()
    await sim.run(steps=10)
    print(sim.get_global_status())


if __name__ == "__main__":
    asyncio.run(main())
