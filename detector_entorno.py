def detectar_entorno_gta(x: float, y: float, z: float) -> str:
    """
    Clasifica automáticamente una coordenada de GTA SA en:
    'mar', 'ciudad', 'desierto' o 'campo'.
    """
    # 1. Detección de Mar / Agua
    if z <= 0.5 or abs(x) >= 2850 or abs(y) >= 2850:
        return "mar"

    # 2. Detección de Ciudades Principales
    # Los Santos (Sureste)
    if (400 <= x <= 2900) and (-2900 <= y <= -400):
        return "ciudad"
    
    # San Fierro (Oeste)
    if (-2900 <= x <= -1000) and (-1200 <= y <= 1600):
        return "ciudad"
    
    # Las Venturas (Noreste)
    if (800 <= x <= 2900) and (500 <= y <= 2900):
        return "ciudad"

    # 3. Detección de Desierto (Noroeste / Bone County / Area 69)
    if (-2900 <= x <= 800) and (500 <= y <= 2900):
        return "desierto"

    # 4. Campo / Bosques (Red County, Flint County, Mount Chiliad)
    return "campo"