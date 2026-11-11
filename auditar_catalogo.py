"""Auditoria local completa de PNG e identificadores, sin alterar fuentes ni usar APIs."""
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from PIL import Image
from src.catalogo_animaciones import CARPETA, cargar_opciones_animaciones


def auditar():
    tecnicas = cargar_opciones_animaciones()
    ids = {a['id'] for a in tecnicas}
    catalogo = json.loads((CARPETA / 'catalogo.json').read_text(encoding='utf-8'))
    ruta = CARPETA / 'descripciones.json'
    resultados = json.loads(ruta.read_text(encoding='utf-8'))['resultados'] if ruta.exists() else {}
    problemas = []
    categorias = Counter()
    fotos = 0
    sospechosas = 0
    bytes_total = 0
    vistos = set()
    for a in catalogo['animaciones']:
        identificador = f"{a['categoria']}:{a['idx']}:{a['lib']}:{a['anim']}"
        categorias[a['categoria']] += 1
        if identificador not in ids or identificador in vistos:
            problemas.append(dict(id=identificador, tipo='id_inexistente_o_duplicado'))
        vistos.add(identificador)
        if sorted(f['frame'] for f in a['fotogramas']) != list(range(1, 7)):
            problemas.append(dict(id=identificador, tipo='secuencia_incompleta'))
        for f in a['fotogramas']:
            fotos += 1
            archivo = (CARPETA / f['archivo']).resolve()
            if not archivo.is_relative_to(CARPETA.resolve()):
                problemas.append(dict(id=identificador, tipo='ruta_fuera_del_catalogo'))
                continue
            try:
                bytes_total += archivo.stat().st_size
                sospechosas += archivo.stat().st_size < 250_000
                with Image.open(archivo) as im:
                    if im.format != 'PNG':
                        raise ValueError('Formato distinto de PNG')
                    im.verify()
            except (OSError, ValueError, SyntaxError) as e:
                problemas.append(dict(id=identificador, archivo=f['archivo'], tipo=type(e).__name__))
            if fotos % 500 == 0:
                print(f'Comprobadas {fotos} imagenes...', flush=True)
    informe = dict(fecha=datetime.now().isoformat(timespec='seconds'),
        animaciones_tecnicas=len(tecnicas), animaciones_con_capturas=len(vistos),
        ids_sin_capturas=sorted(ids-vistos), descripciones_huerfanas=sorted(set(resultados)-ids),
        fotos=fotos, gb=round(bytes_total/1e9, 2), categorias=dict(categorias),
        descripciones=len(resultados), pendientes_visuales=len(ids-set(resultados)),
        descripciones_por_revisar=sum(a['analisis']['requiere_revision'] for a in resultados.values()),
        fotos_sospechosas_por_tamano=sospechosas,
        nota='Integridad PNG no implica contenido util. Tamano bajo es solo una heuristica, no un detector de fotos azules.',
        problemas=problemas)
    salida = CARPETA / 'informe_integridad.json'
    salida.write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in informe.items() if k not in ('categorias','problemas')},ensure_ascii=False))
    print(f'Problemas estructurales: {len(problemas)}. Informe: {salida}')


if __name__ == '__main__':
    auditar()
