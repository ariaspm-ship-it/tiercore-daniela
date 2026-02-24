# simulator/resort_simulator.py
# Simulador completo del resort (191 viviendas, chillers, etc.)

import random
import time
from datetime import datetime, timedelta
from typing import Dict, List

from core.config import Config
from core.logger import simulator_logger
from devices.chiller import Chiller, ChillerData
from devices.room import Room, RoomData
from devices.villa import Villa, VillaData
from devices.heat_machine import HeatMachine, HeatMachineData
from devices.inverter import Inverter, InverterData
from generators.habitaciones import HABITACIONES
from generators.villas import VILLAS

class ResortSimulator:
    """
    Simulador del resort completo
    Genera datos realistas para todas las viviendas y equipos
    """
    
    def __init__(self):
        self.habitaciones = HABITACIONES
        self.villas = VILLAS
        self.timestamp = datetime.now()
        self.running = False
        
        # Inicializar chillers
        self.chillers = [
            Chiller("2CH-1", "Chiller RTAG-01", "192.168.1.101"),
            Chiller("2CH-2", "Chiller RTAG-02", "192.168.1.102"),
            Chiller("2CH-3", "Chiller RTAG-03", "192.168.1.103")
        ]
        
        # Inicializar heat machines
        self.heat_machines = [
            HeatMachine("CXAU-1", "Heat Machine 1", "192.168.1.201"),
            HeatMachine("CXAU-2", "Heat Machine 2", "192.168.1.202")
        ]
        
        # Inicializar inversores
        self.inversores = [
            Inverter("INV-A1", "Solar A1", "Roof Building A"),
            Inverter("INV-A2", "Solar A2", "Roof Building A"),
            Inverter("INV-C1", "Solar C1", "Roof Building C"),
            Inverter("INV-C2", "Solar C2", "Roof Building C"),
            Inverter("INV-C3", "Solar C3", "Roof Building C")
        ]
        
        self.stats = {
            "total_lecturas": 0,
            "fugas_detectadas": 0,
            "alertas_generadas": 0
        }
        
        simulator_logger.info("Simulador del resort inicializado")
        simulator_logger.info(f"🏢 {len(self.habitaciones)} habitaciones")
        simulator_logger.info(f"🏡 {len(self.villas)} villas")
        simulator_logger.info(f"❄️ {len(self.chillers)} chillers")
        simulator_logger.info(f"🔥 {len(self.heat_machines)} heat machines")
        simulator_logger.info(f"☀️ {len(self.inversores)} inversores")
    
    def generar_lectura_habitacion(self, room: Room) -> RoomData:
        """Genera lectura realista para una habitación"""
        
        hora = self.timestamp.hour
        dia_semana = self.timestamp.weekday()
        
        # Factor según hora del día
        if 0 <= hora < 6:  # Madrugada
            factor_elec = random.uniform(0.1, 0.3)
            factor_agua = random.uniform(0, 0.1)
        elif 7 <= hora < 10:  # Mañana (duchas)
            factor_elec = random.uniform(0.3, 0.6)
            factor_agua = random.uniform(0.4, 1.2)
        elif 18 <= hora < 23:  # Noche
            factor_elec = random.uniform(0.5, 1.0)
            factor_agua = random.uniform(0.3, 0.8)
        else:  # Resto
            factor_elec = random.uniform(0.2, 0.4)
            factor_agua = random.uniform(0.1, 0.3)
        
        # Factor según día (fin de semana más consumo)
        if dia_semana >= 5:  # Sábado/Domingo
            factor_elec *= 1.2
            factor_agua *= 1.3
        
        # Añadir aleatoriedad
        factor_elec *= random.uniform(0.8, 1.2)
        factor_agua *= random.uniform(0.8, 1.2)
        
        # Detectar fugas (probabilidad 0.5% por lectura)
        fuga = random.random() < 0.005
        if fuga:
            factor_agua *= random.uniform(3, 8)
            self.stats["fugas_detectadas"] += 1
        
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
        """Genera lectura realista para una villa"""
        
        hora = self.timestamp.hour
        mes = self.timestamp.month
        
        # Consumo base más alto que apartamentos
        factor_elec = random.uniform(1.5, 3.0)
        factor_agua = random.uniform(0.5, 1.5)
        
        # Piscina (solo en horas de calor y meses cálidos)
        if 10 <= hora <= 20 and mes in [4,5,6,7,8,9,10]:
            pool_kwh = random.uniform(2.0, 4.0)
        else:
            pool_kwh = 0
        
        # Riego (temprano o tarde)
        if hora in [6,7,8,18,19,20]:
            riego_m3 = random.uniform(0.3, 0.8)
        else:
            riego_m3 = 0
        
        # Añadir aleatoriedad
        factor_elec *= random.uniform(0.9, 1.1)
        factor_agua *= random.uniform(0.9, 1.1)
        
        return VillaData(
            timestamp=self.timestamp,
            electricity_kwh=round(factor_elec + pool_kwh, 2),
            water_cold_m3=round(factor_agua, 2),
            water_hot_m3=round(factor_agua * 0.4, 2),
            pool_kwh=round(pool_kwh, 2),
            irrigation_m3=round(riego_m3, 2),
            fuga_detectada=random.random() < 0.002  # menos probable que aptos
        )
    
    def generar_lectura_chiller(self, chiller: Chiller, idx: int) -> ChillerData:
        """Genera lectura realista para un chiller"""
        
        hora = self.timestamp.hour
        temp_ext = 28 + random.uniform(-3, 3)
        
        # Demanda según hora
        if 12 <= hora < 16:
            demanda = 450 + random.uniform(-30, 30)
        elif 0 <= hora < 6:
            demanda = 180 + random.uniform(-20, 20)
        else:
            demanda = 280 + random.uniform(-40, 40)
        
        # Chiller 3 es standby (alterna)
        if chiller.id == "2CH-3":
            if random.random() < 0.3:  # 30% apagado
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
        
        # COP objetivo entre 3.5 y 4.2
        cop_objetivo = 3.8 + random.uniform(-0.2, 0.4)
        power = round(demanda / cop_objetivo, 1)
        flow = round(demanda / (5 * 1.16), 1)  # delta T 5°C aprox
        
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
        """Genera lectura para heat machine"""
        
        hora = self.timestamp.hour
        
        # Demanda de ACS
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
        """Genera lectura para inversor solar"""
        
        hora = self.timestamp.hour
        mes = self.timestamp.month
        
        # Solo produce de día
        if 7 <= hora <= 18:
            # Potencia según hora del día
            if 11 <= hora <= 14:  # Mediodía
                potencia = 15 + random.uniform(-2, 5)
            elif 9 <= hora <= 16:  # Horas centrales
                potencia = 10 + random.uniform(-3, 4)
            else:  # Amanecer/atardecer
                potencia = 3 + random.uniform(-1, 2)
            
            # Factor según mes (verano más producción)
            if mes in [6,7,8]:
                potencia *= 1.2
            elif mes in [12,1,2]:
                potencia *= 0.6
        else:
            potencia = 0
        
        return InverterData(
            timestamp=self.timestamp,
            power_kw=round(potencia, 1),
            voltage=round(400 + random.uniform(-10, 10), 1),
            current=round(potencia * 2.5, 1),  # aprox
            grid_power_kw=round(potencia * 0.95, 1),
            temperature=round(35 + random.uniform(-5, 15), 1),
            efficiency=round(95 + random.uniform(-2, 3), 1),
            status="Funcionando" if potencia > 0.5 else "Standby"
        )
    
    def step(self):
        """Avanza un paso en la simulación"""
        
        self.timestamp += timedelta(minutes=5)
        
        # Actualizar habitaciones
        for room in self.habitaciones:
            data = self.generar_lectura_habitacion(room)
            room.update(data)
        
        # Actualizar villas
        for villa in self.villas:
            data = self.generar_lectura_villa(villa)
            villa.update(data)
        
        # Actualizar chillers
        for i, chiller in enumerate(self.chillers):
            data = self.generar_lectura_chiller(chiller, i)
            chiller.update(data)
        
        # Actualizar heat machines
        for i, hm in enumerate(self.heat_machines):
            data = self.generar_lectura_heat_machine(hm, i)
            hm.update(data)
        
        # Actualizar inversores
        for i, inv in enumerate(self.inversores):
            data = self.generar_lectura_inversor(inv, i)
            inv.update(data)
        
        self.stats["total_lecturas"] += 1
        
        if self.stats["total_lecturas"] % 100 == 0:
            simulator_logger.info(f"Simulación avanzada: {self.stats['total_lecturas']} pasos")
    
    def run(self, steps=None):
        """Ejecuta la simulación"""
        self.running = True
        self.timestamp = datetime.now()
        
        simulator_logger.info("🚀 Simulación iniciada")
        
        try:
            if steps:
                for _ in range(steps):
                    self.step()
                    time.sleep(0.01)  # Pequeña pausa
            else:
                while self.running:
                    self.step()
                    time.sleep(1)  # 1 segundo real = 5 minutos simulación
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        self.running = False
        simulator_logger.info("⏹️ Simulación detenida")
        simulator_logger.info(f"📊 Estadísticas: {self.stats}")
    
    def get_global_status(self):
        """Retorna estado global del resort"""
        
        total_elec = sum(r.last_data.electricity_kwh for r in self.habitaciones if r.last_data)
        total_agua = sum(r.last_data.water_cold_m3 for r in self.habitaciones if r.last_data)
        fugas = sum(1 for r in self.habitaciones if r.fuga_activa)
        
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
            "stats": self.stats
        }

# Para pruebas directas
if __name__ == "__main__":
    sim = ResortSimulator()
    sim.run(steps=10)
    print(sim.get_global_status())
