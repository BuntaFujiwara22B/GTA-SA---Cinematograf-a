from src.paths import DATA_ROOT, RESOURCE_ROOT, FROZEN
"""Biblioteca local. El .mms usa Sounds/<archivo> de la carpeta de su misión."""
import hashlib
import re
import unicodedata
from pathlib import Path

RAIZ=(DATA_ROOT/'music') if FROZEN else RESOURCE_ROOT/'assets/music'
FORMATOS={'.mp3','.wav','.ogg'}


def pistas(categoria):
    carpeta=(RAIZ/categoria).resolve()
    if not carpeta.is_relative_to(RAIZ.resolve()):return []
    return sorted(p.relative_to(RAIZ).as_posix() for p in carpeta.glob('*')
        if p.suffix.lower() in FORMATOS and p.is_file() and p.resolve().is_relative_to(RAIZ.resolve()))


def _resolver_con_datos(pista):
    if not pista:return None
    ruta=(RAIZ/pista).resolve()
    if not ruta.is_relative_to(RAIZ.resolve()) or not ruta.is_file() or ruta.suffix.lower() not in FORMATOS:
        raise ValueError('La pista debe existir dentro de assets/music y ser MP3, WAV u OGG.')
    datos=ruta.read_bytes()
    if not datos:
        raise ValueError('La canción está vacía. Selecciona un archivo de audio con contenido.')
    base=unicodedata.normalize('NFKD',ruta.stem).encode('ascii','ignore').decode()
    # Nombres cortos ASCII: compatibles con los buffers del cargador de audio del mod.
    base=re.sub(r'[^a-zA-Z0-9_-]+','_',base).strip('_')[:16] or 'musica'
    huella=hashlib.sha256(datos).hexdigest()[:10]
    return ruta,f'{base}_{huella}{ruta.suffix.lower()}',datos


def resolver(pista):
    resuelta=_resolver_con_datos(pista)
    return resuelta[:2] if resuelta else None


def configuracion_musica(pista):
    """Contrato GameSet.txt 1.87: reproduce audio global desde Sounds/<nombre>."""
    resuelta=_resolver_con_datos(pista)
    if not resuelta:return {}
    _,nombre,datos=resuelta
    # MUSIC_START es la transición de volumen en segundos, no un interruptor booleano.
    return dict(GAME_MUSIC=nombre,MUSIC_START='1',MUSIC_PROGRESS='0',
                MUSIC_SPEED='1',MUSIC_LOOP='1',MUSIC_SHA256=hashlib.sha256(datos).hexdigest())


def copiar_pista(pista,carpeta_mision):
    resuelta=_resolver_con_datos(pista)
    if not resuelta:return None
    origen,nombre,datos=resuelta
    destino=Path(carpeta_mision)/'Sounds'/nombre
    destino.parent.mkdir(parents=True,exist_ok=True)
    if origen!=destino.resolve():
        try:
            with destino.open('xb') as archivo:archivo.write(datos)
        except FileExistsError:
            if destino.read_bytes()!=datos:
                raise ValueError('Ya existe una copia de audio diferente con el mismo nombre. '
                                 'No se sobrescribió una canción de otra exportación.')
    return destino
