# tests/test_quick.py
# Tests rápidos para verificar el sistema completo

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.config import Config
from generators.habitaciones import generar_habitaciones
from generators.villas import generar_villas
from generators.edificios import crear_edificios
from ai.leak_detector import LeakDetector
from ai.chiller_optimizer import ChillerOptimizer
from devices.chiller import Chiller


def test_habitaciones():
    print("\n" + "=" * 60)
    print("🧪 TEST 1: Generación de habitaciones")
    print("=" * 60)

    habitaciones = generar_habitaciones()
    print(f"✅ Total habitaciones: {len(habitaciones)}")

    a = [r for r in habitaciones if r.id.startswith('A')]
    b = [r for r in habitaciones if r.id.startswith('B')]
    c = [r for r in habitaciones if r.id.startswith('C')]

    print(f"   A: {len(a)}")
    print(f"   B: {len(b)}")
    print(f"   C: {len(c)}")

    ids = [r.id for r in habitaciones]
    duplicados = len(ids) - len(set(ids))
    print(f"   Duplicados: {duplicados}")

    return len(habitaciones) == 187 and duplicados == 0


def test_villas():
    print("\n" + "=" * 60)
    print("🧪 TEST 2: Generación de villas")
    print("=" * 60)

    villas = generar_villas()
    print(f"✅ Total villas: {len(villas)}")

    for v in villas:
        print(f"   {v.id}: {v.nombre}")

    return len(villas) == 4


def test_edificios():
    print("\n" + "=" * 60)
    print("🧪 TEST 3: Estructura de edificios")
    print("=" * 60)

    edificios = crear_edificios()

    total_hab = sum(len(e.habitaciones) for e in edificios.values())
    print(f"✅ Total viviendas: {total_hab}")

    for ed_id, ed in edificios.items():
        print(f"\n🏢 {ed_id}: {ed.nombre}")
        print(f"   Habitaciones: {len(ed.habitaciones)}")
        print(f"   Chillers: {len(ed.chillers)}")
        print(f"   Heat Machines: {len(ed.heat_machines)}")
        print(f"   Inversores: {len(ed.inversores)}")
        print(f"   Paneles: {len(ed.paneles)}")
        print(f"   Puntos BMS estimados: {ed.puntos_bms_estimados}")

    return total_hab == Config.get_total_viviendas()


def test_leak_detector_quick():
    print("\n" + "=" * 60)
    print("🧪 TEST 4: Detector de fugas (rápido)")
    print("=" * 60)

    from devices.room import Room, RoomData
    from datetime import datetime, timedelta
    import random

    detector = LeakDetector()
    room = Room("A301", "A", 3)

    now = datetime.now()
    for i in range(10 * 288):
        ts = now - timedelta(minutes=5 * i)
        hora = ts.hour

        if 2 <= hora <= 5:
            agua = 0.0008
        else:
            agua = random.uniform(0.0002, 0.0005)

        data = RoomData(
            timestamp=ts,
            electricity_kwh=random.uniform(0.2, 0.5),
            water_cold_m3=agua,
            water_hot_m3=agua * 0.3,
            fc_kwh=random.uniform(0.5, 1.0),
            return_temp=45,
            fuga_detectada=False
        )
        room.update(data)

    caudal = detector.calcular_caudal_nocturno(room)
    patron = detector.detectar_patron_fuga(room, dias=3)

    print(f"📊 Caudal nocturno: {caudal:.1f} L/h")
    print(f"📊 Patrón de fuga: {patron['fuga_detectada']}")

    if patron['fuga_detectada']:
        print(f"   Confianza: {patron['confianza'] * 100:.0f}%")
        print(f"   Caudales: {patron['caudales']}")

    return patron['fuga_detectada']


def test_chiller_optimizer_quick():
    print("\n" + "=" * 60)
    print("🧪 TEST 5: Optimizador de chillers (rápido)")
    print("=" * 60)

    optimizer = ChillerOptimizer()
    chillers = [
        Chiller("2CH-1", "Chiller RTAG-01", "192.168.1.101"),
        Chiller("2CH-2", "Chiller RTAG-02", "192.168.1.102"),
        Chiller("2CH-3", "Chiller RTAG-03", "192.168.1.103")
    ]

    from devices.chiller import ChillerData
    from datetime import datetime

    now = datetime.now()
    datos = [
        ChillerData(now, 7.2, 12.5, 124, 452, 3.65, 1, False, 82),
        ChillerData(now, 7.1, 12.4, 118, 460, 3.90, 1, False, 80),
        ChillerData(now, 7.3, 12.6, 45, 158, 3.51, 1, False, 28)
    ]

    for ch, d in zip(chillers, datos):
        ch.update(d)

    resultados = optimizer.optimizar(chillers, temp_exterior=28)

    for r in resultados:
        print(f"\n📊 {r.chiller_id}")
        print(f"   COP actual: {r.cop_actual:.2f}")
        print(f"   Ahorro: {r.ahorro_potencial_euro_dia}€/día")
        print(f"   Recomendación: {r.recomendacion}")

    return len(resultados) == 3


def run_all_tests():
    print("\n🚀 INICIANDO TESTS RÁPIDOS - DANIELA v0.5")
    print("=" * 60)

    tests = [
        ("Habitaciones", test_habitaciones),
        ("Villas", test_villas),
        ("Edificios", test_edificios),
        ("Detector fugas", test_leak_detector_quick),
        ("Optimizador chillers", test_chiller_optimizer_quick)
    ]

    resultados = []
    for nombre, test_func in tests:
        try:
            resultado = test_func()
            resultados.append((nombre, "✅ OK" if resultado else "❌ FALLÓ"))
        except Exception as error:
            resultados.append((nombre, f"❌ ERROR: {error}"))

    print("\n" + "=" * 60)
    print("📊 RESUMEN DE TESTS")
    print("=" * 60)

    todos_ok = True
    for nombre, resultado in resultados:
        print(f"{resultado} - {nombre}")
        if "❌" in resultado:
            todos_ok = False

    print("=" * 60)
    if todos_ok:
        print("🎯 TODOS LOS TESTS PASARON CORRECTAMENTE")
    else:
        print("⚠️ ALGUNOS TESTS FALLARON - REVISAR")

    return todos_ok


if __name__ == "__main__":
    run_all_tests()
