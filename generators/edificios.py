# generators/edificios.py
# Generador de la estructura completa de edificios

from typing import Dict, List

from core.logger import main_logger
from core.config import Config
from devices.room import Room
from devices.chiller import Chiller
from devices.heat_machine import HeatMachine
from devices.inverter import Inverter
from devices.panel import crear_paneles_proyecto

from generators.habitaciones import generar_habitaciones
from generators.villas import generar_villas


class Edificio:
    """Representa un edificio del complejo"""

    def __init__(self, id: str, nombre: str, habitaciones: List[Room] = None,
                 chillers: List[Chiller] = None, heat_machines: List[HeatMachine] = None,
                 inversores: List[Inverter] = None):
        self.id = id
        self.nombre = nombre
        self.habitaciones = habitaciones or []
        self.chillers = chillers or []
        self.heat_machines = heat_machines or []
        self.inversores = inversores or []
        self.paneles = []

    @property
    def total_habitaciones(self) -> int:
        return len(self.habitaciones)

    @property
    def puntos_bms_estimados(self) -> int:
        puntos = 0
        puntos += self.total_habitaciones * 5
        puntos += len(self.chillers) * 10
        puntos += len(self.heat_machines) * 8
        puntos += len(self.inversores) * 6
        puntos += len(self.paneles) * 15
        return puntos


def crear_edificios() -> Dict[str, Edificio]:
    todas_habitaciones = generar_habitaciones()
    todas_villas = generar_villas()

    hab_a = [r for r in todas_habitaciones if r.id.startswith('A')]
    hab_b = [r for r in todas_habitaciones if r.id.startswith('B')]
    hab_c = [r for r in todas_habitaciones if r.id.startswith('C')]

    chillers_a = [
        Chiller("2CH-1", "Chiller RTAG-01", "192.168.10.10"),
        Chiller("2CH-2", "Chiller RTAG-02", "192.168.10.11"),
        Chiller("2CH-3", "Chiller RTAG-03", "192.168.10.12")
    ]

    heat_machines_a = [
        HeatMachine("CXAU-1", "Heat Machine 1", "192.168.10.20"),
        HeatMachine("CXAU-2", "Heat Machine 2", "192.168.10.21")
    ]

    inversores_a = [
        Inverter("INV-A1", "Solar A1", "Roof Building A"),
        Inverter("INV-A2", "Solar A2", "Roof Building A")
    ]

    inversores_c = [
        Inverter("INV-C1", "Solar C1", "Roof Building C"),
        Inverter("INV-C2", "Solar C2", "Roof Building C"),
        Inverter("INV-C3", "Solar C3", "Roof Building C")
    ]

    edificio_a = Edificio(
        id="A",
        nombre="Building A - Residences & Spa",
        habitaciones=hab_a,
        chillers=chillers_a,
        heat_machines=heat_machines_a,
        inversores=inversores_a
    )

    edificio_b = Edificio(
        id="B",
        nombre="Building B - Residences",
        habitaciones=hab_b
    )

    edificio_c = Edificio(
        id="C",
        nombre="Building C - Residences & Pool",
        habitaciones=hab_c,
        inversores=inversores_c
    )

    villas_edificio = Edificio(
        id="V",
        nombre="Villas de Lujo",
        habitaciones=todas_villas
    )

    gestor_paneles = crear_paneles_proyecto()
    for panel in gestor_paneles.get_all_panels():
        if 'A' in panel.id:
            edificio_a.paneles.append(panel)
        elif 'B' in panel.id:
            edificio_b.paneles.append(panel)
        elif 'C' in panel.id:
            edificio_c.paneles.append(panel)
        else:
            villas_edificio.paneles.append(panel)

    edificios = {
        'A': edificio_a,
        'B': edificio_b,
        'C': edificio_c,
        'V': villas_edificio
    }

    total_hab = sum(len(e.habitaciones) for e in edificios.values())
    assert total_hab == Config.get_total_viviendas(), f"Total habitaciones incorrecto: {total_hab}"

    main_logger.info("=" * 60)
    main_logger.info("🏢 ESTRUCTURA DE EDIFICIOS COMPLETADA")
    main_logger.info("=" * 60)

    for ed_id, ed in edificios.items():
        main_logger.info(f"{ed_id}: {ed.nombre}")
        main_logger.info(f"   Habitaciones: {ed.total_habitaciones}")
        main_logger.info(f"   Chillers: {len(ed.chillers)}")
        main_logger.info(f"   Heat Machines: {len(ed.heat_machines)}")
        main_logger.info(f"   Inversores: {len(ed.inversores)}")
        main_logger.info(f"   Paneles: {len(ed.paneles)}")
        main_logger.info(f"   Puntos BMS estimados: {ed.puntos_bms_estimados}")

    total_puntos = sum(e.puntos_bms_estimados for e in edificios.values())
    main_logger.info("=" * 60)
    main_logger.info(f"📊 TOTAL PUNTOS BMS ESTIMADOS: ~{total_puntos}")
    main_logger.info("=" * 60)

    return edificios


def get_total_puntos_logicos() -> int:
    puntos_fisicos = 1400
    puntos_logicos = 700
    return puntos_fisicos + puntos_logicos


def get_building_summary(building_id: str) -> Dict:
    edificios = crear_edificios()
    ed = edificios.get(building_id)

    if not ed:
        return {}

    return {
        'id': ed.id,
        'nombre': ed.nombre,
        'habitaciones': ed.total_habitaciones,
        'chillers': len(ed.chillers),
        'heat_machines': len(ed.heat_machines),
        'inversores': len(ed.inversores),
        'paneles': len(ed.paneles),
        'puntos_bms': ed.puntos_bms_estimados
    }


__all__ = ['Edificio', 'crear_edificios', 'get_total_puntos_logicos', 'get_building_summary']
