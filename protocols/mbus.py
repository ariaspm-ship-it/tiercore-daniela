# protocols/mbus.py
# Cliente M-Bus (EN 13757) para lectura de contadores de energía, agua y calorías

import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime
import random

from core.logger import protocols_logger
from core.config import Config


# ---------------------------------------------------------------------------
# BCH-VILLA COLONY RESORT — mapa de contadores M-Bus
# 85 contadores físicos distribuidos entre Edificios A, B, C
#
# Rangos de dirección primaria (1 byte, 0-250, EN 13757-2 §7.4):
#   Edificio A : 1  – 50   (10 zonas × 5 tipos de contador)
#   Edificio B : 51 – 70   ( 4 zonas × 5 tipos de contador)
#   Edificio C : 71 – 85   ( 3 zonas × 5 tipos de contador)
#
# Tipo de contador por offset dentro de cada grupo de 5:
#   0 → electric      Energía eléctrica    (kWh acumulado)
#   1 → water_cold    Agua fría            (m³ acumulado)
#   2 → water_hot     Agua caliente        (m³ acumulado)
#   3 → fc_calories   Calorías fan-coil    (kWh acumulado)
#   4 → hw_return     Retorno ACS          (°C + m³ acumulado)
# ---------------------------------------------------------------------------

_METER_TYPES = ("electric", "water_cold", "water_hot", "fc_calories", "hw_return")

# Value Information Field (VIF) según EN 13757-3 §8.4.3
_VIF_MAP: Dict[str, int] = {
    "electric":    0x07,  # Wh × 10^4  → kWh
    "water_cold":  0x15,  # m³ × 10^-1
    "water_hot":   0x15,  # m³ × 10^-1
    "fc_calories": 0x07,  # Wh × 10^4  → kWh térmico
    "hw_return":   0x5A,  # Return temperature (°C × 10^-1)
}

# Código de medio EN 13757-2 (byte 5 de dirección secundaria)
_MEDIUM_MAP: Dict[str, int] = {
    "electric":    0x02,  # Electricidad
    "water_cold":  0x07,  # Agua fría
    "water_hot":   0x06,  # Agua caliente
    "fc_calories": 0x04,  # Calor (calorímetro)
    "hw_return":   0x04,  # Calor (sensor de retorno)
}


def _build_meter_map() -> Dict[int, Dict[str, Any]]:
    """
    Construye la tabla de 85 contadores BCH.
    Retorna {primary_address: {building, zone, meter_type, medium, vif, serial}}
    """
    meter_map: Dict[int, Dict[str, Any]] = {}

    # Edificio A — zonas A1..A10, direcciones 1-50
    for zone in range(1, 11):
        for offset, mtype in enumerate(_METER_TYPES):
            addr = (zone - 1) * 5 + offset + 1
            meter_map[addr] = {
                "building":     "A",
                "zone":         f"A-Z{zone:02d}",
                "meter_type":   mtype,
                "medium":       _MEDIUM_MAP[mtype],
                "vif":          _VIF_MAP[mtype],
                "manufacturer": "BCH",
                "serial":       f"A{zone:02d}{offset:02d}000",
            }

    # Edificio B — zonas B1..B4, direcciones 51-70
    for zone in range(1, 5):
        for offset, mtype in enumerate(_METER_TYPES):
            addr = 50 + (zone - 1) * 5 + offset + 1
            meter_map[addr] = {
                "building":     "B",
                "zone":         f"B-Z{zone:02d}",
                "meter_type":   mtype,
                "medium":       _MEDIUM_MAP[mtype],
                "vif":          _VIF_MAP[mtype],
                "manufacturer": "BCH",
                "serial":       f"B{zone:02d}{offset:02d}000",
            }

    # Edificio C — zonas C1..C3, direcciones 71-85
    for zone in range(1, 4):
        for offset, mtype in enumerate(_METER_TYPES):
            addr = 70 + (zone - 1) * 5 + offset + 1
            meter_map[addr] = {
                "building":     "C",
                "zone":         f"C-Z{zone:02d}",
                "meter_type":   mtype,
                "medium":       _MEDIUM_MAP[mtype],
                "vif":          _VIF_MAP[mtype],
                "manufacturer": "BCH",
                "serial":       f"C{zone:02d}{offset:02d}000",
            }

    return meter_map


# Singleton construido una sola vez al importar el módulo
BCH_METER_MAP: Dict[int, Dict[str, Any]] = _build_meter_map()


def _room_to_base_address(room_id: str) -> Optional[int]:
    """
    Deriva la dirección M-Bus base (tipo electric) de una habitación.

    Edificio A (10 zonas, addrs 1-50)  → zone_idx = room_num % 10
    Edificio B ( 4 zonas, addrs 51-70) → zone_idx = room_num % 4
    Edificio C ( 3 zonas, addrs 71-85) → zone_idx = room_num % 3

    Los 5 contadores de la habitación son base+0..base+4
    (electric, water_cold, water_hot, fc_calories, hw_return).
    """
    if not room_id:
        return None

    building = room_id[0].upper()

    try:
        room_num = int(room_id[1:])
    except (ValueError, IndexError):
        return None

    if building == "A":
        zone_idx = room_num % 10          # 0-9
        return zone_idx * 5 + 1           # 1, 6, 11, …, 46
    if building == "B":
        zone_idx = room_num % 4           # 0-3
        return 50 + zone_idx * 5 + 1      # 51, 56, 61, 66
    if building == "C":
        zone_idx = room_num % 3           # 0-2
        return 70 + zone_idx * 5 + 1      # 71, 76, 81

    return None


class MBusClient:
    """
    Cliente M-Bus (EN 13757) para lectura de contadores de energía,
    agua fría/caliente, calorías de fan-coil y temperatura de retorno.

    Modos de operación
    ------------------
    simulacion : Config.MODO_SIMULACION = True  (por defecto)
                 Genera lecturas coherentes con BCH sin necesidad de hardware.
    real       : stub — implementar con pyMBus cuando hardware disponible.

    Estándar   : EN 13757-2 (capa de enlace) + EN 13757-3 (capa de aplicación)
    Baudrate   : 2 400 bps  (Config.MBUS_BAUDRATE, conforme IEC 870-5-2)
    Dirección  : Primaria 0-250 (1 byte) o secundaria 8 bytes
    """

    # Caracteres de trama EN 13757-2
    START_SHORT  = 0xE5   # ACK / trama corta
    START_LONG   = 0x68   # trama larga / control
    STOP_BYTE    = 0x16
    FC_REQ_UD2   = 0x5B   # Request User Data 2 (lectura)
    FC_SND_NKE   = 0x40   # Inicializar esclavo
    FC_SND_UD    = 0x53   # Enviar User Data

    def __init__(
        self,
        serial_port: str = None,
        baudrate: int = None,
        timeout: float = 2.0,
    ):
        self.serial_port = serial_port
        self.baudrate = baudrate or Config.MBUS_BAUDRATE  # 2 400 bps
        self.timeout = timeout
        self.connected = False
        self.mode = "real" if serial_port else "simulacion"

        # Estado acumulado simulado: {address: {field: value}}
        self._sim_state: Dict[int, Dict[str, float]] = {}
        self._init_simulated_data()

        protocols_logger.info(
            f"M-Bus cliente inicializado (modo={self.mode}, baud={self.baudrate})"
        )

    def _init_simulated_data(self):
        """
        Pre-carga valores acumulados realistas para los 85 contadores BCH.
        Usa semilla fija (42) para reproducibilidad entre sesiones.
        """
        rng = random.Random(42)

        for addr, meta in BCH_METER_MAP.items():
            mtype = meta["meter_type"]

            if mtype == "electric":
                self._sim_state[addr] = {
                    "energy_kwh": rng.uniform(4_000, 18_000),
                    "flow_lph":   rng.uniform(500, 4_500),    # W equivalente L/h
                    "temperature": rng.uniform(18, 28),
                }
            elif mtype == "water_cold":
                self._sim_state[addr] = {
                    "volume_m3":  rng.uniform(80, 600),
                    "flow_lph":   rng.uniform(5, 80),
                    "temperature": rng.uniform(12, 18),
                }
            elif mtype == "water_hot":
                self._sim_state[addr] = {
                    "volume_m3":  rng.uniform(30, 300),
                    "flow_lph":   rng.uniform(2, 40),
                    "temperature": rng.uniform(45, 60),
                }
            elif mtype == "fc_calories":
                self._sim_state[addr] = {
                    "energy_kwh": rng.uniform(2_000, 12_000),
                    "flow_lph":   rng.uniform(100, 1_200),
                    "temperature": rng.uniform(7, 14),        # agua fría suministro °C
                }
            elif mtype == "hw_return":
                self._sim_state[addr] = {
                    "volume_m3":  rng.uniform(25, 200),
                    "flow_lph":   rng.uniform(2, 30),
                    "temperature": rng.uniform(42, 55),       # retorno ACS °C
                }

    async def connect(self) -> bool:
        if Config.MODO_SIMULACION:
            await asyncio.sleep(0.05)
            self.connected = True
            protocols_logger.info("M-Bus modo simulacion activado")
            return True

        # TODO: implement with pyMBus when hardware available
        protocols_logger.warning(
            "M-Bus modo real no implementado — "
            "instalar pyMBus y configurar puerto serie"
        )
        return False

    async def disconnect(self):
        self.connected = False
        protocols_logger.info("M-Bus desconectado")

    async def read_meter(self, address: int) -> Optional[Dict[str, Any]]:
        """
        Lee un contador M-Bus por su dirección primaria (0-250).

        EN 13757-3 §6: Variable Data Structure — cada campo tiene su propio
        DIF (Data Information Field) y VIF (Value Information Field).

        Retorna
        -------
        {
            "address":    int,
            "meter_type": str,    # electric | water_cold | water_hot |
                                  #           fc_calories | hw_return
            "building":   str,
            "zone":       str,
            "energy_kwh": float | None,   # acumulado energía (kWh)
            "volume_m3":  float | None,   # acumulado volumen (m³)
            "flow_lph":   float,          # caudal instantáneo (L/h)
            "temperature": float,         # temperatura (°C)
            "timestamp":  str,
        }
        """
        if address not in BCH_METER_MAP:
            protocols_logger.warning(
                f"M-Bus: dirección {address} no registrada en BCH_METER_MAP"
            )
            return None

        if not self.connected and not Config.MODO_SIMULACION:
            await self.connect()

        meta = BCH_METER_MAP[address]
        mtype = meta["meter_type"]

        if Config.MODO_SIMULACION:
            await asyncio.sleep(0.02)

            state = self._sim_state[address]

            reading: Dict[str, Any] = {
                "address":     address,
                "meter_type":  mtype,
                "building":    meta["building"],
                "zone":        meta["zone"],
                "energy_kwh":  None,
                "volume_m3":   None,
                "flow_lph":    max(0.0, state["flow_lph"] + random.uniform(-5, 5)),
                "temperature": state["temperature"] + random.uniform(-0.5, 0.5),
                "timestamp":   datetime.now().isoformat(),
            }

            if mtype in ("electric", "fc_calories"):
                reading["energy_kwh"] = state["energy_kwh"] + random.uniform(0.01, 0.15)
                self._sim_state[address]["energy_kwh"] = reading["energy_kwh"]

            if mtype in ("water_cold", "water_hot", "hw_return"):
                reading["volume_m3"] = state["volume_m3"] + random.uniform(0.001, 0.010)
                self._sim_state[address]["volume_m3"] = reading["volume_m3"]

            self._sim_state[address]["flow_lph"] = reading["flow_lph"]

            protocols_logger.debug(
                f"M-Bus read addr={address} type={mtype} "
                f"E={reading['energy_kwh']} V={reading['volume_m3']} "
                f"F={reading['flow_lph']:.1f} T={reading['temperature']:.1f}"
            )
            return reading

        # TODO: implement with pyMBus when hardware available
        protocols_logger.warning("M-Bus modo real no implementado")
        return None

    async def read_room_meters(self, room_id: str) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Lee los 5 tipos de contador M-Bus para una habitación.

        Retorna
        -------
        {
            "electric":    {..., energy_kwh, flow_lph, temperature},
            "water_cold":  {..., volume_m3,  flow_lph, temperature},
            "water_hot":   {..., volume_m3,  flow_lph, temperature},
            "fc_calories": {..., energy_kwh, flow_lph, temperature},
            "hw_return":   {..., volume_m3,  flow_lph, temperature},
        }
        """
        base = _room_to_base_address(room_id)
        if base is None:
            protocols_logger.warning(
                f"M-Bus: room_id '{room_id}' sin mapeo de dirección — "
                "edificio no soportado o ID inválido"
            )
            return {mtype: None for mtype in _METER_TYPES}

        results: Dict[str, Optional[Dict[str, Any]]] = {}
        for offset, mtype in enumerate(_METER_TYPES):
            results[mtype] = await self.read_meter(base + offset)

        protocols_logger.debug(
            f"M-Bus read_room_meters room={room_id} base_addr={base}"
        )
        return results

    async def discover_devices(self) -> List[Dict[str, Any]]:
        """
        Descubre todos los contadores M-Bus en el bus.

        EN 13757-2 §7: procedimiento SND_NKE (broadcast) seguido de
        REQ_UD2 para cada dirección primaria 0-250.

        En modo simulación retorna el mapa completo de 85 contadores BCH.

        Retorna lista de:
            {address, building, zone, meter_type, medium, vif, serial, manufacturer}
        """
        if Config.MODO_SIMULACION:
            await asyncio.sleep(0.5)  # simula tiempo de escaneo del bus serie

            devices = [
                {
                    "address":      addr,
                    "building":     meta["building"],
                    "zone":         meta["zone"],
                    "meter_type":   meta["meter_type"],
                    "medium":       meta["medium"],
                    "vif":          meta["vif"],
                    "serial":       meta["serial"],
                    "manufacturer": meta["manufacturer"],
                }
                for addr, meta in sorted(BCH_METER_MAP.items())
            ]

            count_a = sum(1 for d in devices if d["building"] == "A")
            count_b = sum(1 for d in devices if d["building"] == "B")
            count_c = sum(1 for d in devices if d["building"] == "C")
            protocols_logger.info(
                f"M-Bus discovery: {len(devices)} contadores encontrados "
                f"(A={count_a}, B={count_b}, C={count_c})"
            )
            return devices

        # TODO: implement with pyMBus when hardware available
        protocols_logger.warning("M-Bus modo real no implementado")
        return []


async def ejemplo_uso():
    client = MBusClient()
    await client.connect()

    devices = await client.discover_devices()
    print(f"Contadores descubiertos: {len(devices)}")

    reading = await client.read_meter(1)
    print(f"Lectura contador #1: {reading}")

    room_data = await client.read_room_meters("A301")
    for mtype, data in room_data.items():
        print(f"  {mtype}: {data}")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(ejemplo_uso())
