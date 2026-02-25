# protocols/modbus.py
# Cliente Modbus TCP/RTU para comunicación con inversores, paneles, etc.

import asyncio
import struct
from typing import Dict, Any, Optional, List
from datetime import datetime
import random

from core.logger import protocols_logger
from core.config import Config


class ModbusClient:
    """
    Cliente Modbus para comunicación TCP/RTU
    Versión simulada para prototipo
    """

    FUNC_READ_COILS = 1
    FUNC_READ_DISCRETE_INPUTS = 2
    FUNC_READ_HOLDING_REGISTERS = 3
    FUNC_READ_INPUT_REGISTERS = 4
    FUNC_WRITE_SINGLE_COIL = 5
    FUNC_WRITE_SINGLE_REGISTER = 6
    FUNC_WRITE_MULTIPLE_REGISTERS = 16

    def __init__(self, host: str = None, port: int = 502,
                 serial_port: str = None, baudrate: int = 9600,
                 unit_id: int = 1, timeout: int = 5):
        self.host = host
        self.port = port
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.unit_id = unit_id
        self.timeout = timeout
        self.connected = False
        self.mode = 'TCP' if host else 'RTU' if serial_port else 'simulacion'

        self.simulated_registers = {}
        self._init_simulated_data()

        protocols_logger.info(f"Cliente Modbus inicializado (modo={self.mode})")

    def _init_simulated_data(self):
        for i in range(1, 6):
            base = i * 100
            self.simulated_registers[base] = 15000 + i * 500
            self.simulated_registers[base + 1] = 400
            self.simulated_registers[base + 2] = 38
            self.simulated_registers[base + 3] = 97
            self.simulated_registers[base + 4] = 35

        for i in range(1, 10):
            base = 1000 + i * 10
            self.simulated_registers[base] = 480
            self.simulated_registers[base + 1] = 482
            self.simulated_registers[base + 2] = 479
            self.simulated_registers[base + 3] = 124
            self.simulated_registers[base + 4] = 122
            self.simulated_registers[base + 5] = 125

    async def connect(self) -> bool:
        if Config.MODO_SIMULACION:
            await asyncio.sleep(0.1)
            self.connected = True
            protocols_logger.info(f"🔌 Modbus {self.mode} conectado (simulado)")
            return True

        protocols_logger.warning("Modbus modo real no implementado")
        return False

    async def disconnect(self):
        self.connected = False
        protocols_logger.info("Modbus desconectado")

    async def read_holding_registers(self, address: int, count: int = 1) -> Optional[List[int]]:
        if not self.connected and not Config.MODO_SIMULACION:
            await self.connect()

        if Config.MODO_SIMULACION:
            await asyncio.sleep(0.05)

            result = []
            for i in range(count):
                reg_addr = address + i
                if reg_addr in self.simulated_registers:
                    value = self.simulated_registers[reg_addr]
                    value += int(random.uniform(-10, 10))
                    result.append(value)
                else:
                    result.append(random.randint(0, 1000))

            return result

        return None

    async def read_input_registers(self, address: int, count: int = 1) -> Optional[List[int]]:
        return await self.read_holding_registers(address, count)

    async def write_register(self, address: int, value: int) -> bool:
        if Config.MODO_SIMULACION:
            await asyncio.sleep(0.05)
            self.simulated_registers[address] = value
            protocols_logger.debug(f"Escritura Modbus: {address} = {value}")
            return True

        return False

    async def read_float32(self, address: int, big_endian: bool = True) -> Optional[float]:
        registers = await self.read_holding_registers(address, 2)
        if not registers or len(registers) < 2:
            return None

        if big_endian:
            bytes_val = struct.pack('>HH', registers[0], registers[1])
        else:
            bytes_val = struct.pack('<HH', registers[0], registers[1])

        return struct.unpack('>f', bytes_val)[0] if big_endian else struct.unpack('<f', bytes_val)[0]

    async def read_inverter_data(self, inverter_id: int) -> Dict[str, Any]:
        base_addr = inverter_id * 100

        data = {
            'power_w': await self.read_holding_registers(base_addr),
            'voltage_dc': await self.read_holding_registers(base_addr + 1),
            'current_dc': await self.read_holding_registers(base_addr + 2),
            'efficiency': await self.read_holding_registers(base_addr + 3),
            'temperature': await self.read_holding_registers(base_addr + 4),
            'timestamp': datetime.now().isoformat()
        }

        for key, value in data.items():
            if isinstance(value, list) and value:
                data[key] = value[0]

        return data


async def ejemplo_uso():
    client = ModbusClient(host='192.168.1.100', port=502)
    await client.connect()

    data = await client.read_inverter_data(1)
    print(f"Datos inversor: {data}")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(ejemplo_uso())
