"""Elimina únicamente copias byte a byte de las carpetas antiguas importadas."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def limpiar(root,aplicar=False):
    root=Path(root).resolve();assets=(root/'assets').resolve()
    if not assets.is_relative_to(root):raise ValueError('Ruta de assets fuera del proyecto.')
    conocidos={}
    for carpeta in ('vehicles','objects'):
        for p in (assets/carpeta).glob('*.png'):
            conocidos[hashlib.sha256(p.read_bytes()).hexdigest()]=p
    cambios=[]
    for carpeta in ('Vehículos','Objetos'):
        anterior=(assets/carpeta).resolve()
        if not anterior.is_relative_to(assets):raise ValueError('Carpeta fuera de assets.')
        for p in anterior.glob('*.png'):
            if not p.resolve().is_relative_to(anterior):continue
            huella=hashlib.sha256(p.read_bytes()).hexdigest()
            if huella not in conocidos:continue
            cambios.append(dict(eliminado=str(p.relative_to(root)),conservado=str(conocidos[huella].relative_to(root)),bytes=p.stat().st_size,sha256=huella))
            if aplicar:p.unlink()
        if aplicar and anterior.exists() and not any(anterior.iterdir()):anterior.rmdir()
    return cambios


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--aplicar',action='store_true');args=parser.parse_args()
    cambios=limpiar(ROOT,args.aplicar)
    salida=ROOT/'evaluaciones/limpieza.json';salida.parent.mkdir(exist_ok=True)
    salida.write_text(json.dumps(dict(aplicado=args.aplicar,copias=cambios),ensure_ascii=False,indent=2),encoding='utf-8')
    print(f"{len(cambios)} duplicados; {sum(c['bytes'] for c in cambios)/1024**2:.1f} MiB {'liberados' if args.aplicar else 'recuperables'}.")
