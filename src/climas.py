from src.paths import RESOURCE_ROOT
from src.datos_cache import leer_json
"""IDs de eWeatherType de GTA SA y fotos con asociacion explicita, nunca por posicion."""
import json
from pathlib import Path

ASSETS = RESOURCE_ROOT / 'assets'
NOMBRES = (
    'Muy soleado · Los Santos','Soleado · Los Santos',
    'Muy soleado con contaminación · Los Santos','Soleado con contaminación · Los Santos',
    'Nublado · Los Santos','Soleado · San Fierro','Muy soleado · San Fierro',
    'Nublado · San Fierro','Lluvia · San Fierro','Niebla · San Fierro',
    'Soleado · Las Venturas','Muy soleado · Las Venturas','Nublado · Las Venturas',
    'Muy soleado · Campo','Soleado · Campo','Nublado · Campo','Lluvia · Campo',
    'Muy soleado · Desierto','Soleado · Desierto','Tormenta de arena',
    'Efecto submarino','Colores especiales 1','Colores especiales 2',
)


def foto_verificada(hora, clima_id):
    manifiesto = ASSETS / 'climas_catalogo.json'
    if not manifiesto.exists():
        return None
    datos = leer_json(manifiesto)
    for p in datos.get('previews', []):
        if p.get('verificado') is True and p.get('hora') == hora % 24 and p.get('clima_id') == clima_id:
            ruta = (ASSETS / p['archivo']).resolve()
            if ruta.is_relative_to(ASSETS.resolve()) and ruta.is_file():
                return ruta.relative_to(ASSETS.resolve()).as_posix()
    return None


def preview_clima(hora, clima_id):
    """Asociación explícita de captura; un orden completo no prueba el clima visual."""
    manifiesto=ASSETS/'climas_catalogo.json'
    if not manifiesto.exists():
        return None
    datos=leer_json(manifiesto)
    for p in datos.get('previews',[]):
        if p.get('hora')!=hora%24 or p.get('clima_id')!=clima_id:
            continue
        if not (p.get('verificado') is True or p.get('asociacion') in ('tanda_con_captura_inicial','estimacion_visual_secuencial')):
            continue
        ruta=(ASSETS/p['archivo']).resolve()
        if ruta.is_relative_to(ASSETS.resolve()) and ruta.is_file():
            return dict(p,archivo=ruta.relative_to(ASSETS.resolve()).as_posix())
    return None


def clima_con_foto(hora, preferido, direccion=1):
    """Salta huecos conservando el ID real de la captura elegida."""
    paso=1 if direccion>=0 else -1
    for desplazamiento in range(len(NOMBRES)):
        candidato=(preferido+paso*desplazamiento)%len(NOMBRES)
        if preview_clima(hora,candidato) is not None:
            return candidato
    return None
