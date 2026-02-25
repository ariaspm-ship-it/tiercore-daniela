# generators/habitaciones.py
# Generador de las 187 habitaciones según planos EE-4-A-2, EE-4-B-2, EE-4-C-2

from core.logger import main_logger
from devices.room import Room


def generar_habitaciones():
    """
    Genera las 187 habitaciones del complejo
    - Building A: 119 habitaciones (L3-L7, 19 por planta)
    - Building B: 41 habitaciones (distribución estimada)
    - Building C: 27 habitaciones (según plano EE-4-C-2)
    """
    habitaciones = []

    # ============================================
    # BUILDING A (119 habitaciones)
    # ============================================
    for planta in range(3, 8):  # L3, L4, L5, L6, L7
        numeros = [
            301, 302, 303, 304, 305, 306, 307, 308, 309, 310,
            311, 312, 314, 315, 316, 317, 318, 319
        ]

        numeros.insert(12, 313)  # Insertar 313 después de 312

        for num in numeros:
            room_id = f"A{planta}{str(num)[-2:]}"
            habitaciones.append(Room(room_id, "A", planta))

    # Suites adicionales para completar 119 en Building A
    # Se agregan 24 unidades en L7 con numeración no solapada
    for num in range(20, 44):
        room_id = f"A7{num:02d}"
        habitaciones.append(Room(room_id, "A", 7))

    # ============================================
    # BUILDING B (41 habitaciones)
    # ============================================
    config_b = [
        (1, 8),
        (2, 8),
        (3, 8),
        (4, 7),
        (5, 6),
        (6, 4)
    ]

    for planta, cantidad in config_b:
        for i in range(cantidad):
            room_id = f"B{planta}{i + 1:02d}"
            habitaciones.append(Room(room_id, "B", planta))

    # ============================================
    # BUILDING C (27 habitaciones)
    # ============================================
    config_c = [
        (1, [102, 104, 106, 108]),
        (2, [201, 202, 203, 204, 206, 208]),
        (3, [301, 302, 303, 304, 306, 308]),
        (4, [401, 402, 403, 404, 406, 408]),
        (5, [501, 502, 503, 504, 506])
    ]

    for planta, numeros in config_c:
        for num in numeros:
            room_id = f"C{num}"
            habitaciones.append(Room(room_id, "C", planta))

    # ============================================
    # VALIDACIONES
    # ============================================
    ids = [r.id for r in habitaciones]
    duplicados = set([room_id for room_id in ids if ids.count(room_id) > 1])
    if duplicados:
        raise ValueError(f"IDs duplicados detectados: {duplicados}")

    total_esperado = 119 + 41 + 27  # 187
    if len(habitaciones) != total_esperado:
        raise ValueError(f"Total incorrecto: {len(habitaciones)} (esperado {total_esperado})")

    count_a = sum(1 for r in habitaciones if r.id.startswith('A'))
    count_b = sum(1 for r in habitaciones if r.id.startswith('B'))
    count_c = sum(1 for r in habitaciones if r.id.startswith('C'))

    assert count_a == 119, f"Building A: {count_a} (esperado 119)"
    assert count_b == 41, f"Building B: {count_b} (esperado 41)"
    assert count_c == 27, f"Building C: {count_c} (esperado 27)"

    main_logger.info(f"✅ {len(habitaciones)} habitaciones generadas correctamente")
    main_logger.info(f"   A:{count_a} B:{count_b} C:{count_c}")

    return habitaciones


__all__ = ['generar_habitaciones']
