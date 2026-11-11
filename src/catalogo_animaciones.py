from src.paths import RESOURCE_ROOT
from src.datos_cache import leer_json
"""Opciones tecnicas completas y evidencia visual disponible, sin consultas API."""
import hashlib
import json
import re
from pathlib import Path

ROOT = RESOURCE_ROOT
CARPETA = ROOT / 'assets/animations/catalogo_completo'
CATEGORIAS = {
    'STAND': 'posturas de pie', 'SIT': 'posturas sentadas',
    'LAY': 'posturas tumbadas', 'WEAPON': 'acciones con armas',
    'CHAT': 'gestos y conversaciones', 'HURT': 'reacciones a golpes',
    'DANCE': 'baile', 'MIMIC': 'expresiones', 'INTERACT': 'interacciones',
    'SEX': 'interacciones intimas', 'MOVE': 'movimiento',
    'CUTS': 'acciones de cinematicas', 'ATTACK': 'ataques', 'DEATH': 'caidas y muertes',
}


def cargar_opciones_animaciones():
    texto = (ROOT / 'src/todo.txt').read_text(encoding='utf-8').split('anim list', 1)[1]
    opciones = []
    for cat in CATEGORIAS:
        bloque = re.search(r'^\[' + cat + r'\]\s*\n(.*?)(?=^\[|\Z)', texto, re.M | re.S)
        if bloque is None:
            raise ValueError('Falta categoria de animaciones: ' + cat)
        filas = re.findall(r'^\s*(\d+)\s*=\s*([^,\r\n]+),\s*([^\r\n]+)', bloque[1], re.M)
        total = int(re.search(r'TOTAL\s*=\s*(\d+)', bloque[1], re.I)[1])
        if len(filas) != total or [int(f[0]) for f in filas] != list(range(1, total + 1)):
            raise ValueError('Indices incompletos en ' + cat)
        for idx, anim, lib in filas:
            opciones.append(dict(id=f'{cat}:{int(idx)}:{lib.strip()}:{anim.strip()}',
                categoria=cat, idx=int(idx), anim=anim.strip(), lib=lib.strip()))
    return opciones


def cargar_contexto_animaciones():
    opciones = cargar_opciones_animaciones()
    ids = {o['id'] for o in opciones}
    visuales = []
    ruta = CARPETA / 'descripciones.json'
    catalogo = CARPETA / 'catalogo.json'
    if ruta.exists() and catalogo.exists():
        datos = leer_json(ruta)
        if datos.get('huella_catalogo') == hashlib.sha256(catalogo.read_bytes()).hexdigest():
            for identificador, resultado in datos.get('resultados', {}).items():
                if identificador not in ids:
                    continue
                a = resultado['analisis']
                visuales.append(dict(id=identificador, observado=a['descripcion_visual'],
                    interpretacion=a['interpretacion'], etiquetas=a['etiquetas'],
                    confianza=a['confianza'], requiere_revision=a['requiere_revision'],
                    frames_utiles=len(a['frames_utiles']), limitaciones=a['limitaciones']))
    return (
        '\nOPCIONES DE ANIMACION COMPLETAS: todas proceden del todo.txt actual.\n'
        'Cada opcion se expresa categoria:indice:biblioteca:nombre. '
        'animacion_sugerida debe ser EXACTAMENTE uno de estos identificadores, o null si no hay una opcion adecuada. '
        'El indice solo no identifica una animacion. No inventes IDs ni bibliotecas.\n'
        'Puedes proponer opciones sin descripcion visual usando el significado del nombre tecnico y la categoria, '
        'pero eso es una inferencia: no prueba que el movimiento coincida. '
        'Prefiere evidencia visual suficiente, confianza alta/media y sin revision. '
        'Las entradas con revision o baja confianza se pueden considerar como candidatas inciertas, '
        'sin afirmar que su interpretacion esta confirmada. No conviertas objetos/parejas ausentes en funciones disponibles. '
        'No supongas velocidad, duracion ni que el movimiento sea un bucle. '
        'Si una escena requiere certeza que los datos no permiten, no inventes una animacion.\n'
        'CATEGORIAS (orientacion general, no descripcion de cada movimiento): '
        + json.dumps(CATEGORIAS, ensure_ascii=False)
        + '\nIDS DISPONIBLES:\n' + '\n'.join(o['id'] for o in opciones)
        + '\nEVIDENCIA VISUAL AUTOMATICA DISPONIBLE (puede contener errores):\n'
        + json.dumps(visuales, ensure_ascii=False, separators=(',', ':')))
