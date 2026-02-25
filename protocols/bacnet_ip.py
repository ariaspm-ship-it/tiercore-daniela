# protocols/bacnet_ip.py
# Cliente BACnet/IP para comunicación con dispositivos IP

import asyncio
import socket
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import random

from core.logger import protocols_logger
from core.config import Config


class BACnetIPClient:
    """
    Cliente BACnet/IP para comunicación con dispositivos BACnet
    Versión simulada para prototipo (sin dependencias externas)
    """

    OBJECT_TYPES = {
        0: 'analogInput',
        1: 'analogOutput',
        2: 'analogValue',
        3: 'binaryInput',
        4: 'binaryOutput',
        5: 'binaryValue',
        8: 'device',
        9: 'file'
    }

    PROPERTIES = {
        75: 'objectName',
        77: 'presentValue',
        79: 'description',
        85: 'statusFlags',
        116: 'units'
    }

    def __init__(self, local_ip: str = '0.0.0.0', port: int = 47808, device_id: int = 1):
        self.local_ip = local_ip
        self.port = port
        self.device_id = device_id
        self.sock = None
        self.devices = {}
        self.subscriptions = {}
        self.running = False
        self.timeout = 5

        self.simulated_data = {}
        self._init_simulated_data()

        protocols_logger.info(f"BACnet/IP cliente inicializado (simulado) en puerto {port}")

    def _init_simulated_data(self):
        self.simulated_data = {
            'chiller_1_temp_supply': 7.2,
            'chiller_1_temp_return': 12.5,
            'chiller_1_power': 124.5,
            'chiller_1_cop': 3.8,
            'chiller_1_alarm': 0,
            'chiller_2_temp_supply': 7.1,
            'chiller_2_temp_return': 12.4,
            'chiller_2_power': 118.2,
            'chiller_2_cop': 3.9,
            'chiller_2_alarm': 0,
            'chiller_3_temp_supply': 7.3,
            'chiller_3_temp_return': 12.6,
            'chiller_3_power': 0,
            'chiller_3_cop': 0,
            'chiller_3_alarm': 0,
            'mdp_a_480_power': 245.6,
            'mdp_a_208_power': 98.3,
            'mdp_b_power': 124.5,
            'mdp_c_power': 87.2,
        }

    def connect(self) -> bool:
        if Config.MODO_SIMULACION:
            protocols_logger.info("🔌 BACnet/IP modo simulación activado")
            return True

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind((self.local_ip, self.port))
            self.sock.setblocking(False)
            protocols_logger.info(f"✅ Socket BACnet/IP abierto en puerto {self.port}")
            return True
        except Exception as error:
            protocols_logger.error(f"❌ Error abriendo socket BACnet/IP: {error}")
            return False

    async def read_property(self, device_ip: str, device_port: int,
                            object_type: int, instance: int, property_id: int) -> Optional[Any]:
        if Config.MODO_SIMULACION:
            await asyncio.sleep(0.1)

            if object_type == 0:
                if instance == 1:
                    return 7.2 + random.uniform(-0.2, 0.2)
                if instance == 2:
                    return 12.5 + random.uniform(-0.2, 0.2)
                if instance == 3:
                    return 124.5 + random.uniform(-5, 5)
                if instance == 4:
                    return 3.8 + random.uniform(-0.1, 0.1)

            return random.uniform(0, 100)

        protocols_logger.warning("BACnet/IP modo real no implementado")
        return None

    async def write_property(self, device_ip: str, device_port: int,
                             object_type: int, instance: int, property_id: int,
                             value: Any) -> bool:
        if Config.MODO_SIMULACION:
            await asyncio.sleep(0.1)
            protocols_logger.info(f"✅ Escritura simulada: {device_ip}:{object_type},{instance} = {value}")
            return True

        protocols_logger.warning("BACnet/IP modo real no implementado")
        return False

    async def discover_devices(self, broadcast_ip: str = '255.255.255.255') -> List[Dict]:
        if Config.MODO_SIMULACION:
            await asyncio.sleep(1)

            devices = [
                {'ip': '192.168.10.10', 'port': 47808, 'device_id': 1001, 'name': 'Chiller RTAG-01'},
                {'ip': '192.168.10.11', 'port': 47808, 'device_id': 1002, 'name': 'Chiller RTAG-02'},
                {'ip': '192.168.10.12', 'port': 47808, 'device_id': 1003, 'name': 'Chiller RTAG-03'},
                {'ip': '192.168.10.20', 'port': 47808, 'device_id': 2001, 'name': 'MDP-A-480'},
                {'ip': '192.168.10.21', 'port': 47808, 'device_id': 2002, 'name': 'MDP-A-208'},
                {'ip': '192.168.20.10', 'port': 47808, 'device_id': 3001, 'name': 'MDP-B'},
                {'ip': '192.168.30.10', 'port': 47808, 'device_id': 4001, 'name': 'MDP-C'},
            ]

            self.devices = {d['device_id']: d for d in devices}
            protocols_logger.info(f"✅ Descubiertos {len(devices)} dispositivos BACnet")
            return devices

        return []

    async def read_chiller_points(self, chiller_ip: str, chiller_id: str) -> Dict[str, Any]:
        points = {}

        if Config.MODO_SIMULACION:
            await asyncio.sleep(0.2)

            if '1' in chiller_id:
                points = {
                    'temp_supply': 7.2 + random.uniform(-0.2, 0.2),
                    'temp_return': 12.5 + random.uniform(-0.2, 0.2),
                    'power_kw': 124.5 + random.uniform(-5, 5),
                    'cop': 3.8 + random.uniform(-0.1, 0.1),
                    'compressor_status': 1,
                    'alarm': 0
                }
            elif '2' in chiller_id:
                points = {
                    'temp_supply': 7.1 + random.uniform(-0.2, 0.2),
                    'temp_return': 12.4 + random.uniform(-0.2, 0.2),
                    'power_kw': 118.2 + random.uniform(-5, 5),
                    'cop': 3.9 + random.uniform(-0.1, 0.1),
                    'compressor_status': 1,
                    'alarm': 0
                }
            else:
                points = {
                    'temp_supply': 7.3 + random.uniform(-0.2, 0.2),
                    'temp_return': 12.6 + random.uniform(-0.2, 0.2),
                    'power_kw': random.uniform(0, 10) if random.random() > 0.7 else 0,
                    'cop': 3.7 if random.random() > 0.7 else 0,
                    'compressor_status': 1 if random.random() > 0.7 else 0,
                    'alarm': 0
                }

            points['timestamp'] = datetime.now().isoformat()

        return points

    async def subscribe_cov(self, device_id: int, object_type: int, instance: int,
                            callback: Callable, interval: int = 0) -> str:
        sub_id = f"{device_id}-{object_type}-{instance}-{datetime.now().timestamp()}"

        self.subscriptions[sub_id] = {
            'device_id': device_id,
            'object_type': object_type,
            'instance': instance,
            'callback': callback,
            'interval': interval,
            'last_value': None,
            'timestamp': datetime.now()
        }

        protocols_logger.info(f"✅ Suscripción COV creada: {sub_id}")
        return sub_id

    async def monitor_subscriptions(self):
        self.running = True
        protocols_logger.info("🔄 Monitor COV iniciado")

        while self.running:
            for sub_id, sub in self.subscriptions.items():
                try:
                    new_value = await self.read_property(
                        '192.168.1.1', 47808,
                        sub['object_type'], sub['instance'], 77
                    )

                    if new_value != sub['last_value']:
                        sub['last_value'] = new_value
                        if sub['callback']:
                            await sub['callback'](sub_id, new_value)

                except Exception as error:
                    protocols_logger.error(f"Error en subscription {sub_id}: {error}")

            await asyncio.sleep(5)

    def stop(self):
        self.running = False
        protocols_logger.info("⏹️ Monitor COV detenido")
        if self.sock:
            self.sock.close()


async def ejemplo_uso():
    client = BACnetIPClient()
    client.connect()

    devices = await client.discover_devices()
    print(f"Dispositivos encontrados: {len(devices)}")

    chiller_data = await client.read_chiller_points('192.168.10.10', '2CH-1')
    print(f"Datos chiller: {chiller_data}")

    return client


if __name__ == "__main__":
    asyncio.run(ejemplo_uso())
