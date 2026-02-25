# tests/test_habitaciones.py
# Tests para validar la generación de habitaciones

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from generators.habitaciones import generar_habitaciones
from core.config import Config


class TestHabitaciones(unittest.TestCase):
    """Tests para validar la generación de habitaciones"""

    def setUp(self):
        self.habitaciones = generar_habitaciones()

    def test_total_habitaciones(self):
        self.assertEqual(
            len(self.habitaciones),
            187,
            f"Total incorrecto: {len(self.habitaciones)} (esperado 187)"
        )

    def test_sin_duplicados(self):
        ids = [r.id for r in self.habitaciones]
        duplicados = set([room_id for room_id in ids if ids.count(room_id) > 1])
        self.assertEqual(len(duplicados), 0, f"IDs duplicados: {duplicados}")

    def test_distribucion_edificios(self):
        a = [r for r in self.habitaciones if r.id.startswith('A')]
        b = [r for r in self.habitaciones if r.id.startswith('B')]
        c = [r for r in self.habitaciones if r.id.startswith('C')]

        self.assertEqual(len(a), 119, f"Building A: {len(a)} (esperado 119)")
        self.assertEqual(len(b), 41, f"Building B: {len(b)} (esperado 41)")
        self.assertEqual(len(c), 27, f"Building C: {len(c)} (esperado 27)")

    def test_formato_ids(self):
        for room in self.habitaciones:
            self.assertTrue(room.id[0] in ['A', 'B', 'C'], f"ID inválido: {room.id}")
            self.assertTrue(len(room.id) >= 4, f"ID demasiado corto: {room.id}")

    def test_plantas_validas(self):
        for room in self.habitaciones:
            self.assertTrue(1 <= room.planta <= 7, f"Planta inválida: {room.id} planta {room.planta}")

    def test_config_coincide(self):
        self.assertEqual(Config.EDIFICIOS['A']['habitaciones'], 119)
        self.assertEqual(Config.EDIFICIOS['B']['habitaciones'], 41)
        self.assertEqual(Config.EDIFICIOS['C']['habitaciones'], 27)
        self.assertEqual(Config.EDIFICIOS['V']['villas'], 4)


if __name__ == '__main__':
    unittest.main()
