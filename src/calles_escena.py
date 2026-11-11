from src.paths import RESOURCE_ROOT
from src.datos_cache import leer_json
import json
from pathlib import Path
from PIL import Image
import io

ROOT=RESOURCE_ROOT


def rutas_disponibles():
    p=ROOT/'assets/rutas_calles.json'
    extras=ROOT/'assets/lugares_semanticos.json'
    return (leer_json(p)['rutas'] if p.exists() else [])+(leer_json(extras)['rutas'] if extras.exists() else [])


def elegir_calle(texto,duracion):
    rutas=rutas_disponibles()
    t=texto.lower()
    if 'puente' in t:
        return next((r for r in rutas if 'puente' in r.get('etiquetas',[])),None)
    zona='San Fierro' if 'san fierro' in t else 'Las Venturas' if 'las venturas' in t else 'Los Santos'
    return min((r for r in rutas if r['zona']==zona),key=lambda r:abs(r['longitud']-max(12,min(60,duracion*1.2))),default=None)


def contexto_calles():
    return '\nRUTAS PEATONALES CANDIDATAS DEL GTA INSTALADO: elige ruta_id_sugerida solo entre estos IDs; nunca inventes coordenadas. Mapa orientado norte arriba, limites -3000..3000. No son rutas libres de colisiones confirmadas.\n'+json.dumps(rutas_disponibles(),ensure_ascii=False)


def mapa_para_ia():
    p=ROOT/'assets/locations/sa_map_full.webp'
    if not p.exists():return None
    with Image.open(p) as im:
        im=im.convert('RGB');im.thumbnail((768,768))
        out=io.BytesIO();im.save(out,format='JPEG',quality=80)
        return out.getvalue()
