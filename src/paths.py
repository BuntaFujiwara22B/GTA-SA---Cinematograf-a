"""Recursos de solo lectura y datos del usuario, separados para la distribución."""
import os
import sys
from pathlib import Path

FROZEN=bool(getattr(sys,'frozen',False))
APP_DIR=Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parents[1]
RESOURCE_ROOT=Path(getattr(sys,'_MEIPASS',APP_DIR)) if FROZEN else APP_DIR
ASSETS=RESOURCE_ROOT/'assets'
DATA_ROOT=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'MMS-Director' if FROZEN else APP_DIR
ENV_FILE=DATA_ROOT/'.env'


def salida(root=None):
    return DATA_ROOT if FROZEN else (root or RESOURCE_ROOT)


def vista_asset(relativa):
    """Una vista ligera opcional; nunca altera el archivo fuente del catálogo."""
    relativa=str(relativa).replace('\\','/')
    if relativa.startswith('vehicles/'):
        manifiesto=ASSETS/'vehicles_cutouts/catalogo.json'
        if manifiesto.exists():
            from src.datos_cache import leer_json
            entrada=leer_json(manifiesto).get('resultados',{}).get(relativa,{})
            if entrada.get('usable') and entrada.get('revision_visual'):
                recorte=entrada.get('archivo','')
                p=(ASSETS/recorte).resolve()
                if p.is_relative_to(ASSETS.resolve()) and p.is_file():relativa=recorte
    original=ASSETS/relativa
    try:
        original.resolve().relative_to(ASSETS.resolve())
    except ValueError:
        return relativa
    candidata=ASSETS/'ui'/Path(relativa).with_suffix('.webp')
    return candidata.relative_to(ASSETS).as_posix() if candidata.is_file() else relativa
