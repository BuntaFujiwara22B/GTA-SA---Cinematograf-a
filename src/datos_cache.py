"""Caché acotada que se invalida cuando cambia el archivo, sin sondeos en segundo plano."""
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=24)
def _json(ruta,mtime,tamano):
    return json.loads(Path(ruta).read_text(encoding='utf-8-sig'))


def leer_json(ruta):
    p=Path(ruta).resolve();s=p.stat()
    return _json(str(p),s.st_mtime_ns,s.st_size)
