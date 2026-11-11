"""Busca opciones por nombre o accion en espanol, sin conexion ni cuota."""
import argparse
from src.busqueda_animaciones import buscar_animaciones

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('consulta', nargs='+')
    p.add_argument('--limite', type=int, default=10)
    args = p.parse_args()
    for o in buscar_animaciones(' '.join(args.consulta), args.limite):
        estado = 'candidata por revisar' if o['requiere_revision'] else 'con descripcion sin marca de revision'
        print(f"{o['id']} | {estado} | coincidencias: {', '.join(o['coincidencias'])}")
