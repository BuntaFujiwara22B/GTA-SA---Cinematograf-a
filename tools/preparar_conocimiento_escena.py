"""Importa metadatos de personajes del juego sin API y sin alterar GTA."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def preparar(gta):
    archivo = Path(gta) / 'data/peds.ide'
    actores = []
    for linea in archivo.read_text(encoding='latin-1').splitlines():
        campos = [v.strip() for v in linea.split('#', 1)[0].split(',')]
        if len(campos) < 6 or not campos[0].isdigit(): continue
        modelo = int(campos[0])
        if not (ROOT / f'assets/actors/{modelo}.png').exists(): continue
        tipo = campos[3]
        roles = ['civil']
        if tipo == 'COP': roles = ['militar' if modelo == 287 else 'policia']
        elif tipo == 'CRIMINAL' or tipo.startswith('GANG'): roles = ['criminal']
        if modelo in (158, 161): roles = ['granjero']
        if modelo in (274, 275, 276): roles = ['paramedico']
        if modelo in (277, 278, 279): roles = ['bombero']
        if modelo in (71, 163, 164): roles = ['guardia']
        actores.append(dict(model_id=modelo, nombre=campos[1], tipo_juego=tipo, roles=roles,
            foto=f'actors/{modelo}.png'))
    salida = ROOT / 'assets/personajes_roles.json'
    salida.write_text(json.dumps(dict(origen='data/peds.ide del GTA instalado; uniformes y skins rurales contrastados con las capturas',
        nota='Criminal es un rol narrativo y una categoría del juego, no una inferencia moral por apariencia.',
        actores=actores), ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{len(actores)} personajes con metadatos: {salida.name}')


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--gta', required=True)
    preparar(p.parse_args().gta)
