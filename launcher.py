"""Entrada de escritorio y comprobación del paquete sin abrir ventanas."""
import json
import os
import sys
from pathlib import Path
from src.paths import RESOURCE_ROOT,ASSETS,DATA_ROOT,FROZEN
os.environ.setdefault('HF_HUB_DISABLE_PROGRESS_BARS','1')
os.environ.setdefault('TOKENIZERS_PARALLELISM','false')


def diagnostico():
    from src.catalogo_animaciones import cargar_opciones_animaciones
    from src.catalogos_entidades import disponibles
    import main
    return dict(recursos=str(RESOURCE_ROOT),congelado=FROZEN,animaciones=len(cargar_opciones_animaciones()),
        actores=len(list((ASSETS/'actors').glob('*.png'))),vehiculos=len(disponibles('vehicles')),
        objetos=len(disponibles('objects')),flet_cliente=(RESOURCE_ROOT/'flet_client/flet.exe').exists(),
        datos_usuario=str(DATA_ROOT),claves_incluidas=(RESOURCE_ROOT/'.env').exists())


if __name__=='__main__':
    if '--clip-check' in sys.argv:
        try:
            from src.clip_visual import buscar_fotos,vector_texto
            vector_texto('a screenshot of GTA San Andreas at sunset')
            fotos=buscar_fotos('a screenshot of GTA San Andreas at sunset',2)
            datos=dict(clip_funciona=bool(fotos),candidatas=fotos)
        except Exception as error:
            fotos=[]
            datos=dict(clip_funciona=False,error=f'{type(error).__name__}: {error}')
        salida=json.dumps(datos,ensure_ascii=False)
        i=sys.argv.index('--clip-check')
        if len(sys.argv)>i+1:Path(sys.argv[i+1]).write_text(salida,encoding='utf-8')
        elif sys.stdout:print(salida)
        raise SystemExit(0 if fotos else 1)
    if '--self-check' in sys.argv:
        i=sys.argv.index('--self-check')
        datos=diagnostico();salida=json.dumps(datos,ensure_ascii=False,indent=2)
        if len(sys.argv)>i+1:Path(sys.argv[i+1]).write_text(salida,encoding='utf-8')
        elif sys.stdout:print(salida)
        raise SystemExit(0 if datos['actores'] and datos['vehiculos'] and not datos['claves_incluidas'] else 1 if FROZEN else 0)
    DATA_ROOT.mkdir(parents=True,exist_ok=True)
    for c in ('mistica','feliz'):(DATA_ROOT/'music'/c).mkdir(parents=True,exist_ok=True) if FROZEN else None
    if (RESOURCE_ROOT/'flet_client/flet.exe').exists():os.environ['FLET_VIEW_PATH']=str(RESOURCE_ROOT/'flet_client')
    import flet as ft
    from main import main
    ft.run(main,assets_dir=str(ASSETS))
