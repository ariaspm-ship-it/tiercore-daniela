# tests/test_ai.py
# Tests para módulos de IA (detector de fugas, optimizador de chillers)

import unittest
import sys
import os
from datetime import datetime, timedelta
import random

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai.leak_detector import LeakDetector
from ai.chiller_optimizer import ChillerOptimizer
from devices.room import Room, RoomData
from devices.chiller import Chiller, ChillerData


class TestLeakDetector(unittest.TestCase):
    """Tests para el detector de fugas"""

    def setUp(self):
        self.detector = LeakDetector()
        self.room_normal = Room("A301", "A", 3)
        self.room_fuga = Room("A302", "A", 3)

        now = datetime.now()
        for i in range(100):
            ts = now - timedelta(hours=i)
            hora = ts.hour

            if 2 <= hora <= 5:
                agua = 0.0001
            else:
                agua = random.uniform(0.0003, 0.0008)

            data = RoomData(
                timestamp=ts,
                electricity_kwh=random.uniform(0.2, 0.5),
                water_cold_m3=agua,
                water_hot_m3=agua * 0.3,
                fc_kwh=random.uniform(0.5, 1.0),
                return_temp=45,
                fuga_detectada=False
            )
            self.room_normal.update(data)

        for i in range(100):
            ts = now - timedelta(hours=i)
            hora = ts.hour

            if 2 <= hora <= 5:
                agua = 0.0008
            else:
                agua = random.uniform(0.0003, 0.0008)

            data = RoomData(
                timestamp=ts,
                electricity_kwh=random.uniform(0.2, 0.5),
                water_cold_m3=agua,
                water_hot_m3=agua * 0.3,
                fc_kwh=random.uniform(0.5, 1.0),
                return_temp=45,
                fuga_detectada=False
            )
            self.room_fuga.update(data)

    def test_calcular_caudal_nocturno(self):
        caudal_normal = self.detector.calcular_caudal_nocturno(self.room_normal)
        caudal_fuga = self.detector.calcular_caudal_nocturno(self.room_fuga)

        self.assertLess(caudal_normal, 2.0, f"Caudal normal demasiado alto: {caudal_normal}")
        self.assertGreater(caudal_fuga, 2.0, f"Caudal fuga demasiado bajo: {caudal_fuga}")

    def test_detectar_patron_fuga(self):
        patron_normal = self.detector.detectar_patron_fuga(self.room_normal)
        patron_fuga = self.detector.detectar_patron_fuga(self.room_fuga)

        self.assertFalse(patron_normal['fuga_detectada'])
        self.assertTrue(patron_fuga['fuga_detectada'])

    def test_detectar_fugas(self):
        habitaciones = [self.room_normal, self.room_fuga]
        alertas = self.detector.detectar_fugas(habitaciones)

        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0].room_id, "A302")
        self.assertGreater(alertas[0].confianza, 0.5)


class TestChillerOptimizer(unittest.TestCase):
    """Tests para el optimizador de chillers"""

    def setUp(self):
        self.optimizer = ChillerOptimizer()
        self.chillers = [
            Chiller("2CH-1", "Chiller RTAG-01", "192.168.1.101"),
            Chiller("2CH-2", "Chiller RTAG-02", "192.168.1.102"),
            Chiller("2CH-3", "Chiller RTAG-03", "192.168.1.103")
        ]

        now = datetime.now()
        for i in range(200):
            ts = now - timedelta(hours=i)

            for j, ch in enumerate(self.chillers):
                if j == 2:
                    cop = 3.4 + random.uniform(-0.1, 0.1)
                else:
                    cop = 3.8 + random.uniform(-0.1, 0.1)

                data = ChillerData(
                    timestamp=ts,
                    temp_supply=7.0 + random.uniform(-0.2, 0.2),
                    temp_return=12.0 + random.uniform(-0.2, 0.2),
                    power_kw=120 + random.uniform(-5, 5),
                    cooling_kw=450 + random.uniform(-10, 10),
                    cop=cop,
                    compressor_status=1,
                    alarm=False,
                    flow_m3h=80 + random.uniform(-2, 2)
                )
                ch.update(data)

    def test_entrenar_modelo(self):
        for ch in self.chillers:
            modelo = self.optimizer.entrenar_modelo_chiller(ch)
            self.assertIsNotNone(modelo, f"No se pudo entrenar modelo para {ch.id}")

    def test_predecir_demanda(self):
        demanda_punta = self.optimizer.predecir_demanda(14, 30, 1.0)
        demanda_valle = self.optimizer.predecir_demanda(3, 25, 0.5)

        self.assertGreater(demanda_punta, demanda_valle)
        self.assertGreater(demanda_punta, 300)
        self.assertLess(demanda_valle, 200)

    def test_detectar_degradacion(self):
        for ch in self.chillers:
            self.optimizer.entrenar_modelo_chiller(ch)

        degradacion_1 = self.optimizer.detectar_degradacion(self.chillers[0])
        degradacion_3 = self.optimizer.detectar_degradacion(self.chillers[2])

        self.assertFalse(degradacion_1['degradado'])
        self.assertTrue(degradacion_3['degradado'])
        self.assertGreater(degradacion_3['degradacion_pct'], 5)

    def test_optimizar(self):
        resultados = self.optimizer.optimizar(self.chillers, temp_exterior=28)
        self.assertEqual(len(resultados), 3)

        for r in resultados:
            if r.chiller_id == "2CH-3":
                self.assertIn("degradación", r.recomendacion.lower())

    def test_estadisticas_globales(self):
        stats = self.optimizer.get_estadisticas_globales(self.chillers)

        self.assertIn('cop_medio', stats)
        self.assertIn('chillers_degradados', stats)
        self.assertEqual(stats['num_chillers'], 3)


if __name__ == '__main__':
    unittest.main()
