import csv
import json
import sys
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from generators.habitaciones import generar_habitaciones
from generators.villas import generar_villas


PROJECT_PANELS = [
    "MDP-A-480",
    "MDP-A-208",
    "PP-A-L3",
    "PP-A-L4",
    "PP-A-L5",
    "PP-A-L6",
    "PP-A-L7",
    "MDP-B",
    "MDP-C",
    "LP-LND1",
    "LP-LND2",
    "PP-POOL",
]


POINTS_ROOM = [
    ("ROOM", "ELECTRICITY_KWH", "float", "kWh", "modbus"),
    ("ROOM", "WATER_COLD_M3", "float", "m3", "modbus"),
    ("ROOM", "WATER_HOT_M3", "float", "m3", "modbus"),
    ("ROOM", "FC_KWH", "float", "kWh", "modbus"),
    ("ROOM", "RETURN_TEMP_C", "float", "C", "modbus"),
    ("ROOM", "LEAK_ALARM", "bool", "bool", "bacnet"),
    ("ROOM", "OCCUPANCY", "bool", "bool", "bacnet"),
    ("ROOM", "SETPOINT_C", "float", "C", "bacnet"),
    ("ROOM", "HUMIDITY_RH", "float", "%", "bacnet"),
]

POINTS_CHILLER = [
    ("HVAC", "TEMP_SUPPLY_C", "float", "C", "bacnet"),
    ("HVAC", "TEMP_RETURN_C", "float", "C", "bacnet"),
    ("HVAC", "POWER_KW", "float", "kW", "bacnet"),
    ("HVAC", "COOLING_KW", "float", "kW", "bacnet"),
    ("HVAC", "COP", "float", "ratio", "bacnet"),
    ("HVAC", "COMPRESSOR_STATUS", "int", "state", "bacnet"),
    ("HVAC", "ALARM", "bool", "bool", "bacnet"),
    ("HVAC", "FLOW_M3H", "float", "m3/h", "bacnet"),
    ("HVAC", "RUN_HOURS", "float", "h", "bacnet"),
    ("HVAC", "EFFICIENCY_PCT", "float", "%", "bacnet"),
    ("HVAC", "MAINTENANCE_DUE", "bool", "bool", "bacnet"),
    ("HVAC", "AVAILABILITY", "bool", "bool", "bacnet"),
    ("HVAC", "SP_TEMP_SUPPLY_C", "float", "C", "bacnet"),
    ("HVAC", "MODE", "str", "enum", "bacnet"),
]

POINTS_HEAT = [
    ("HVAC", "TEMP_SUPPLY_C", "float", "C", "bacnet"),
    ("HVAC", "TEMP_RETURN_C", "float", "C", "bacnet"),
    ("HVAC", "POWER_KW", "float", "kW", "bacnet"),
    ("HVAC", "HEATING_KW", "float", "kW", "bacnet"),
    ("HVAC", "EFFICIENCY", "float", "ratio", "bacnet"),
    ("HVAC", "PUMP_STATUS", "int", "state", "bacnet"),
    ("HVAC", "ALARM", "bool", "bool", "bacnet"),
    ("HVAC", "RUN_HOURS", "float", "h", "bacnet"),
    ("HVAC", "WATER_FLOW_M3H", "float", "m3/h", "bacnet"),
    ("HVAC", "SP_TEMP_SUPPLY_C", "float", "C", "bacnet"),
    ("HVAC", "AVAILABILITY", "bool", "bool", "bacnet"),
    ("HVAC", "MODE", "str", "enum", "bacnet"),
]

POINTS_INVERTER = [
    ("SOLAR", "POWER_KW", "float", "kW", "modbus"),
    ("SOLAR", "VOLTAGE_DC_V", "float", "V", "modbus"),
    ("SOLAR", "CURRENT_DC_A", "float", "A", "modbus"),
    ("SOLAR", "GRID_POWER_KW", "float", "kW", "modbus"),
    ("SOLAR", "TEMPERATURE_C", "float", "C", "modbus"),
    ("SOLAR", "EFFICIENCY_PCT", "float", "%", "modbus"),
    ("SOLAR", "STATUS", "str", "enum", "modbus"),
    ("SOLAR", "DAILY_YIELD_KWH", "float", "kWh", "modbus"),
    ("SOLAR", "LIFETIME_YIELD_KWH", "float", "kWh", "modbus"),
    ("SOLAR", "ALARM", "bool", "bool", "modbus"),
]

POINTS_PANEL = [
    ("ELEC", "VOLTAGE_L1_V", "float", "V", "modbus"),
    ("ELEC", "VOLTAGE_L2_V", "float", "V", "modbus"),
    ("ELEC", "VOLTAGE_L3_V", "float", "V", "modbus"),
    ("ELEC", "CURRENT_L1_A", "float", "A", "modbus"),
    ("ELEC", "CURRENT_L2_A", "float", "A", "modbus"),
    ("ELEC", "CURRENT_L3_A", "float", "A", "modbus"),
    ("ELEC", "POWER_KW", "float", "kW", "modbus"),
    ("ELEC", "POWER_FACTOR", "float", "ratio", "modbus"),
    ("ELEC", "FREQUENCY_HZ", "float", "Hz", "modbus"),
    ("ELEC", "BREAKER_STATUS", "int", "state", "modbus"),
]

POINTS_SITE = [
    ("SITE", "TOTAL_POWER_KW", "float", "kW", "bacnet"),
    ("SITE", "TOTAL_WATER_M3", "float", "m3", "bacnet"),
]


def _sanitize_unit(unit: str) -> str:
    return unit.replace("-", "_").replace(" ", "_").upper()


def _add_points(
    rows: List[Dict[str, str]],
    protocol_rows: Dict[str, List[Dict[str, str]]],
    building: str,
    unit: str,
    points: List[tuple],
    source: str,
    base_address: int,
    instance_start: int,
) -> tuple[int, int]:
    address = base_address
    instance = instance_start
    unit_code = _sanitize_unit(unit)

    for system, variable, data_type, engineering_unit, protocol in points:
        point_name = f"{building}_{unit_code}_{system}_{variable}"
        row = {
            "point_name": point_name,
            "building": building,
            "unit": unit,
            "system": system,
            "variable": variable,
            "source_type": source,
            "protocol_preferred": protocol,
            "data_type": data_type,
            "engineering_unit": engineering_unit,
            "polling_seconds": "30",
            "writable": "true" if variable.startswith("SP_") else "false",
            "active": "true",
        }

        if protocol == "bacnet":
            row["address"] = str(instance)
            row["address_type"] = "object_instance"
            bacnet_row = {
                "point_name": point_name,
                "object_type": "analogValue" if data_type in {"float", "int"} else "binaryValue",
                "object_instance": instance,
                "property": "presentValue",
                "device_id": 1000 + (ord(building[0]) if building else 0),
                "writable": row["writable"] == "true",
            }
            protocol_rows["bacnet"].append(bacnet_row)
            instance += 1
        else:
            row["address"] = str(address)
            row["address_type"] = "holding_register"
            modbus_row = {
                "point_name": point_name,
                "slave_id": 1,
                "address": address,
                "register_type": "holding",
                "quantity": 2 if data_type == "float" else 1,
                "scale": 1.0,
                "signed": False,
                "writable": row["writable"] == "true",
            }
            protocol_rows["modbus"].append(modbus_row)
            address += 2 if data_type == "float" else 1

        rows.append(row)

    return address, instance


def build_mapping() -> tuple[List[Dict[str, str]], Dict[str, List[Dict[str, str]]]]:
    rows: List[Dict[str, str]] = []
    protocol_rows: Dict[str, List[Dict[str, str]]] = {"bacnet": [], "modbus": []}

    next_modbus = 1
    next_bacnet = 10001

    habitaciones = generar_habitaciones()
    for room in habitaciones:
        next_modbus, next_bacnet = _add_points(
            rows, protocol_rows, room.edificio, room.id, POINTS_ROOM, "room", next_modbus, next_bacnet
        )

    villas = generar_villas()
    for villa in villas:
        next_modbus, next_bacnet = _add_points(
            rows, protocol_rows, "V", villa.id, POINTS_ROOM, "villa", next_modbus, next_bacnet
        )

    for chiller_id in ["2CH-1", "2CH-2", "2CH-3"]:
        next_modbus, next_bacnet = _add_points(
            rows, protocol_rows, "A", chiller_id, POINTS_CHILLER, "chiller", next_modbus, next_bacnet
        )

    for heat_id in ["CXAU-1", "CXAU-2"]:
        next_modbus, next_bacnet = _add_points(
            rows, protocol_rows, "A", heat_id, POINTS_HEAT, "heat_machine", next_modbus, next_bacnet
        )

    for inv_id, building in [
        ("INV-A1", "A"),
        ("INV-A2", "A"),
        ("INV-C1", "C"),
        ("INV-C2", "C"),
        ("INV-C3", "C"),
    ]:
        next_modbus, next_bacnet = _add_points(
            rows, protocol_rows, building, inv_id, POINTS_INVERTER, "inverter", next_modbus, next_bacnet
        )

    for panel_id in PROJECT_PANELS:
        parts = panel_id.split("-")
        building = parts[1] if len(parts) > 1 and len(parts[1]) == 1 else "SITE"
        next_modbus, next_bacnet = _add_points(
            rows, protocol_rows, building, panel_id, POINTS_PANEL, "panel", next_modbus, next_bacnet
        )

    next_modbus, next_bacnet = _add_points(
        rows, protocol_rows, "SITE", "RESORT", POINTS_SITE, "site", next_modbus, next_bacnet
    )

    return rows, protocol_rows


def export_files(base_dir: Path) -> Dict[str, int]:
    rows, protocol_rows = build_mapping()

    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    csv_path = data_dir / "point_mapping.csv"
    bacnet_path = data_dir / "bacnet_objects.json"
    modbus_path = data_dir / "modbus_registers.json"

    fieldnames = [
        "point_name",
        "building",
        "unit",
        "system",
        "variable",
        "source_type",
        "protocol_preferred",
        "address_type",
        "address",
        "data_type",
        "engineering_unit",
        "polling_seconds",
        "writable",
        "active",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with bacnet_path.open("w", encoding="utf-8") as bacnet_file:
        json.dump(protocol_rows["bacnet"], bacnet_file, indent=2, ensure_ascii=False)

    with modbus_path.open("w", encoding="utf-8") as modbus_file:
        json.dump(protocol_rows["modbus"], modbus_file, indent=2, ensure_ascii=False)

    return {
        "points_total": len(rows),
        "bacnet_objects": len(protocol_rows["bacnet"]),
        "modbus_registers": len(protocol_rows["modbus"]),
    }


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent
    totals = export_files(project_root)
    print(
        f"point_mapping.csv generado con {totals['points_total']} filas | "
        f"BACnet: {totals['bacnet_objects']} | Modbus: {totals['modbus_registers']}"
    )
