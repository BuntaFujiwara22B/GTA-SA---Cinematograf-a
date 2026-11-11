"""Prepara solo recursos usados en ejecución. Excluye claves, capturas de investigación y salidas."""
import argparse
import json
import shutil
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]


def copiar_modelo_intenciones(destino):
    """Incluye el clasificador local también en paquetes preparados sin CLIP."""
    fuente=ROOT/'models/intenciones'
    nombres=('metadata.json','pesos.npz')
    presentes=[(fuente/nombre).is_file() for nombre in nombres]
    if not any(presentes):return
    if not all(presentes):
        faltantes=', '.join(nombre for nombre,presente in zip(nombres,presentes) if not presente)
        raise RuntimeError('El modelo de intenciones está incompleto: falta '+faltantes+'. Vuelve a entrenarlo antes de preparar la distribución.')
    salida=Path(destino)/'models/intenciones'
    salida.mkdir(parents=True,exist_ok=True)
    for nombre in nombres:shutil.copy2(fuente/nombre,salida/nombre)


def preparar(destino,clip=True):
    destino.mkdir(parents=True,exist_ok=True)
    for carpeta in ('templates','referencias_mms'):
        for p in (ROOT/carpeta).glob('*'):
            if p.is_file():
                out=destino/carpeta/p.name;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,out)
    for p in [ROOT/'src/todo.txt',ROOT/'comprobar_ruta_mvp.lua']:
        out=destino/p.relative_to(ROOT);out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,out)
    assets=ROOT/'assets'
    archivos=list(assets.glob('*.json'))
    for carpeta in ['actors','vehicles','objects','camaras','heights','locations']+[f'hora_{i}' for i in range(24)]:
        archivos.extend(p for p in (assets/carpeta).glob('*') if p.suffix.lower() in ('.png','.webp','.json'))
    archivos.extend(p for p in (assets/'animations/catalogo_completo').glob('*.json') if p.name in ('catalogo.json','descripciones.json'))
    for p in archivos:
        out=destino/p.relative_to(ROOT);out.parent.mkdir(parents=True,exist_ok=True)
        if p.suffix.lower()=='.png' and p.parent.name.startswith('hora_'):
            if out.exists():continue
            with Image.open(p) as im:
                im=im.convert('RGB');im.thumbnail((1280,720));im.save(out,compress_level=1)
        else:shutil.copy2(p,out)
    if (assets/'ui').exists():shutil.copytree(assets/'ui',destino/'assets/ui',dirs_exist_ok=True)
    if (assets/'fonts').exists():shutil.copytree(assets/'fonts',destino/'assets/fonts',dirs_exist_ok=True)
    for p in (assets/'vehicles_cutouts').glob('*') if (assets/'vehicles_cutouts').exists() else []:
        if p.is_file():
            out=destino/'assets/vehicles_cutouts'/p.name;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,out)
    cliente=Path.home()/'.flet/client/flet-desktop-full-1.0.5/flet'
    if not (cliente/'flet.exe').exists():raise RuntimeError('Falta el cliente de escritorio Flet en la caché local.')
    shutil.copytree(cliente,destino/'flet_client',dirs_exist_ok=True)
    indice=ROOT/'cache/clip_climas.npz'
    if indice.exists():
        (destino/'cache').mkdir(exist_ok=True);shutil.copy2(indice,destino/'cache'/indice.name)
    copiar_modelo_intenciones(destino)
    if clip:
        cache=Path.home()/'.cache/huggingface/hub/models--openai--clip-vit-base-patch32/snapshots'
        fuentes=[p for p in cache.iterdir() if (p/'config.json').exists()]
        if not fuentes:raise RuntimeError('No hay pesos locales CLIP para incluir en el paquete.')
        fuente=fuentes[0];out=destino/'models/clip';out.mkdir(parents=True,exist_ok=True)
        for p in fuente.iterdir():
            if p.is_file():shutil.copy2(p,out/p.name)
    total=sum(p.stat().st_size for p in destino.rglob('*') if p.is_file())
    print(f'Recursos listos: {total/1024**2:.1f} MiB. Sin .env ni música personal.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--sin-clip',action='store_true')
    args=parser.parse_args();preparar(ROOT/'build/resources',not args.sin_clip)
