"""Mide trabajo CPU y E/S, no FPS reales de Flutter/GPU."""
import json
import statistics
import time
from pathlib import Path
from src.paths import ASSETS
from src.datos_cache import leer_json
from src.climas import preview_clima
from src.mvp_plan import comprobaciones_peticion


def medir(f,n=80):
    f();muestras=[]
    for _ in range(n):
        t=time.perf_counter();f();muestras.append((time.perf_counter()-t)*1000)
    return dict(mediana_ms=round(statistics.median(muestras),3),p95_ms=round(sorted(muestras)[int(n*.95)-1],3))


if __name__=='__main__':
    ruta=ASSETS/'climas_catalogo.json'
    d=dict(json_sin_cache=medir(lambda:json.loads(ruta.read_text(encoding='utf-8'))),
        json_con_cache=medir(lambda:leer_json(ruta)),consulta_foto=medir(lambda:preview_clima(21,18)),
        semaforos=medir(lambda:comprobaciones_peticion('dos personas corren por una avenida al atardecer')),
        alcance='Tiempos del proceso Python; no demuestra 60 FPS del renderizado.')
    salida=Path('evaluaciones/rendimiento.json');salida.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(d,ensure_ascii=False))
