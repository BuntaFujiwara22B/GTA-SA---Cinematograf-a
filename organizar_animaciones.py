"""Relaciona una tanda aislada de capturas consecutivas con su CSV MoonLoader.

Conserva originales. No envia imagenes a ninguna API.
"""
import argparse
import csv
import json
import re
import shutil
from pathlib import Path


def organizar(csv_path, origen, destino):
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        registro = list(csv.DictReader(f))
    fallos = [f for f in registro if f["estado"] != "SOLICITADA"]
    filas = [f for f in registro if f["estado"] == "SOLICITADA"]
    if not filas:
        raise ValueError("No hay capturas solicitadas en el registro.")
    fotos = []
    for p in origen.glob("*.png"):
        match = re.search(r"\((\d+)\)$", p.stem)
        if not match:
            raise ValueError(f"Captura sin numero reconocible: {p.name}")
        fotos.append((int(match[1]), p))
    fotos.sort(key=lambda item: item[0])
    if len(fotos) != len(filas):
        raise ValueError(f"Hay {len(fotos)} PNG y {len(filas)} solicitudes; no se puede asignar por orden.")
    if any(b[0] != a[0] + 1 for a, b in zip(fotos, fotos[1:])):
        raise ValueError("La numeracion de capturas tiene saltos.")
    if [int(f["solicitud"]) for f in filas] != list(range(1, len(filas) + 1)):
        raise ValueError("Las solicitudes del CSV no son consecutivas.")
    if destino.exists():
        raise FileExistsError(f"El destino ya existe: {destino}")
    grupos = {}
    plan = []
    for fila, (numero, foto) in zip(filas, fotos):
        identificador = f"{fila['categoria']}_{int(fila['idx']):03d}_{fila['lib']}_{fila['anim']}"
        nombre = fila["nombre_destino"]
        if any(re.fullmatch(r"[A-Za-z0-9_.-]+", s) is None or s in (".", "..")
               for s in (identificador, nombre)):
            raise ValueError("Nombre de salida no permitido.")
        relativa = Path(identificador) / nombre
        if relativa in [p[1] for p in plan]:
            raise ValueError("El CSV repite un nombre de salida.")
        plan.append((foto, relativa))
        grupo = grupos.setdefault(identificador, dict(
            categoria=fila["categoria"], idx=int(fila["idx"]),
            anim=fila["anim"], lib=fila["lib"], descripcion=None,
            estado="pendiente_revision_visual", fotogramas=[]))
        # Heuristica propia de esta tanda: fondo vacio comprime mucho mas.
        # No equivale a una clasificacion visual ni detecta todos los errores.
        sospechosa = foto.stat().st_size < 250_000
        grupo["fotogramas"].append(dict(
            frame=int(fila["frame"]), fase=float(fila["fase"]),
            archivo=relativa.as_posix(), original=str(foto.resolve()),
            captura=numero, bytes=foto.stat().st_size,
            revisar_por_tamano=sospechosa))
    destino.mkdir(parents=True)
    for foto, relativa in plan:
        salida = destino / relativa
        salida.parent.mkdir(exist_ok=True)
        shutil.copy2(foto, salida)
    shutil.copy2(csv_path, destino / "registro_original.csv")
    catalogo = dict(
        version=1, origen=str(origen.resolve()),
        fallos=fallos,
        emparejado="Orden numerico; requiere tanda aislada sin capturas ajenas ni omitidas.",
        advertencia="Secuencias de poses pausadas; no inferir velocidad, duracion ni bucle original.",
        criterio_revision="Menos de 250000 bytes: indicio de captura incompleta, pendiente de revision visual.",
        animaciones=list(grupos.values()))
    (destino / "catalogo.json").write_text(
        json.dumps(catalogo, ensure_ascii=False, indent=2), encoding="utf-8")
    sospechosas = sum(f["revisar_por_tamano"] for g in grupos.values() for f in g["fotogramas"])
    print(f"Copiadas {len(plan)} capturas en {len(grupos)} animaciones; {sospechosas} marcadas para revision.")
    print(destino.resolve() / "catalogo.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("origen", type=Path)
    parser.add_argument("destino", type=Path)
    args = parser.parse_args()
    organizar(args.csv, args.origen, args.destino)
