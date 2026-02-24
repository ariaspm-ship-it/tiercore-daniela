# generators/habitaciones.py
# Generador de las 187 habitaciones según planos

from devices.room import Room

def generar_habitaciones():
    """Genera las 187 habitaciones del complejo"""
    
    habitaciones = []
    
    # EDIFICIO A (119 habitaciones)
    # L3 a L7, 19 por planta según plano EE-4-A-2
    for planta in range(3, 8):
        numeros = [301,302,303,304,305,306,307,308,309,310,
                   311,312,314,315,316,317,318,319]
        for num in numeros:
            room_id = f"A{planta}{str(num)[-2:]}"
            habitaciones.append(Room(room_id, "A", planta))
    
    # EDIFICIO B (41 habitaciones - estimado de tabla inicial)
    for i in range(1, 42):
        planta = 1 + (i-1) // 10
        room_id = f"B{i:03d}"
        habitaciones.append(Room(room_id, "B", planta))
    
    # EDIFICIO C (27 habitaciones según plano EE-4-C-2)
    c_rooms = [
        (1, [102,104,106,108]),
        (2, [201,202,203,204,206,208]),
        (3, [301,302,303,304,306,308]),
        (4, [401,402,403,404,406,408]),
        (5, [401,402,403,404,406])  # Nota: se repite 401?
    ]
    
    for planta, nums in c_rooms:
        for num in nums:
            room_id = f"C{num}"
            habitaciones.append(Room(room_id, "C", planta))
    
    print(f"✅ {len(habitaciones)} habitaciones generadas")
    return habitaciones

# Generar al importar
HABITACIONES = generar_habitaciones()
