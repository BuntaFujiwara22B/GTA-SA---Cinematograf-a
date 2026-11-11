from src.paths import RESOURCE_ROOT
from src.datos_cache import leer_json
"""Busqueda local de candidatas; las pistas tecnicas no son descripciones visuales."""
import json
import re
import unicodedata

from src.catalogo_animaciones import CARPETA, CATEGORIAS, cargar_opciones_animaciones

# Traducciones conservadoras de fragmentos explicitos del nombre de animacion.
REGLAS = [
    (r'handsup', 'manos arriba levantar manos rendirse rendicion'),
    (r'roadcross', 'mirar lados cruzar calle'),
    (r'phone', 'telefono llamar llamada hablar celular'),
    (r'smk|smoke|cig', 'fumar cigarrillo'),
    (r'drnk|drink', 'beber tomar bebida'),
    (r'eat|burger|chicken|pizza', 'comer comida'),
    (r'vomit', 'vomitar vomito'),
    (r'panic', 'panico miedo asustado asustarse'),
    (r'clap', 'aplaudir aplausos'),
    (r'dance|dancing', 'bailar baile'),
    (r'wave', 'saludar saludo'),
    (r'chat|talk', 'hablar conversar conversacion'),
    (r'sit|seated', 'sentar sentarse sentado silla'),
    (r'walk', 'caminar caminando andar'),
    (r'(^|_)run($|_)', 'correr corriendo carrera'),
    (r'jump|jmp', 'saltar salto'),
    (r'climb', 'trepar escalar subir'),
    (r'fall', 'caer caida cayendo'),
    (r'getup', 'levantarse incorporar levantando'),
    (r'carry', 'cargar transportar llevar'),
    (r'drunk', 'borracho ebrio tambalearse'),
    (r'reload|rld', 'recargar recarga arma'),
    (r'fire|shoot|sht', 'disparar disparo arma'),
    (r'punch|fight', 'golpear pelear pelea'),
    (r'kick', 'patear patada'),
    (r'knife', 'cuchillo'),
    (r'death|die|dead|deth', 'morir muerte muerto'),
    (r'hit|dmg', 'golpe dolor herido'),
    (r'scratch', 'rascar rascarse'),
    (r'lean', 'apoyarse inclinarse'),
    (r'(^|_)cry($|_)|(^|_)weep($|_)', 'llorar llanto'),
    (r'kiss', 'besar beso'),
    (r'cards', 'cartas naipes'),
    (r'roulette', 'ruleta'),
    (r'barserve|barman|barcustom', 'barra bar camarero atender servir'),
]
STOP = {'el','la','los','las','un','una','unos','unas','de','del','al','a','en','y','o',
        'que','quiero','necesito','personaje','npc','hombre','mujer','esta','este','se','con','por','para'}


def normalizar(texto):
    texto = re.sub(r'([a-z])([A-Z])', r'\1 \2', texto)
    return ''.join(c for c in unicodedata.normalize('NFD', texto.lower()) if not unicodedata.combining(c))


def palabras(texto):
    normal=normalizar(texto)
    tokens=set(re.findall(r'[a-z0-9]+',normal)) - STOP
    for patron,palabra in ((r'\b(?:fum\w*|furm\w*)\b','fumar'),(r'\b(?:bebe|beben|bebiendo)\b','beber'),
        (r'\b(?:come|comen|comiendo)\b','comer'),(r'\b(?:rie|rien|riendo|risa)\b','reir')):
        if re.search(patron,normal):tokens.add(palabra)
    return tokens


def pistas_tecnicas(opcion):
    # No usar biblioteca para deducir acciones: BD_FIRE no implica disparar.
    nombre = opcion['anim'].lower()
    return [etiquetas for patron, etiquetas in REGLAS if re.search(patron, nombre)]


def buscar_animaciones(consulta, limite=12):
    tokens = palabras(consulta)
    if not tokens or limite <= 0:
        return []
    visuales = {}
    ruta = CARPETA / 'descripciones.json'
    if ruta.exists():
        visuales = leer_json(ruta).get('resultados', {})
    encontradas = []
    for o in cargar_opciones_animaciones():
        pistas = pistas_tecnicas(o)
        tecnico = palabras(o['anim'] + ' ' + ' '.join(pistas))
        coincidencias = sorted(tokens & tecnico)
        puntos = 5 * len(coincidencias)
        analisis = visuales.get(o['id'], {}).get('analisis')
        visual = set()
        if analisis:
            visual = palabras(' '.join(analisis['etiquetas']) + ' ' + analisis['descripcion_visual'])
            puntos += (4 if not analisis['requiere_revision'] else 2) * len(tokens & visual)
        # La categoria orienta, pero no basta para recomendar una accion concreta.
        if puntos == 0:
            continue
        puntos += len(tokens & palabras(CATEGORIAS[o['categoria']]))
        encontradas.append(dict(**o, puntuacion=puntos,
            coincidencias=sorted(set(coincidencias) | (tokens & visual)),
            pistas_nombre=pistas,
            fuente='nombre_tecnico_y_categoria' if analisis is None else 'nombre_y_descripcion_automatica',
            requiere_revision=analisis is None or analisis['requiere_revision']))
    from src.capacidades_escena import candidata_aprendida
    aprendida = candidata_aprendida(consulta)
    if aprendida:
        opcion = aprendida[1]
        evidencia = opcion['aprendizaje_supervisado']
        existente = next((o for o in encontradas if o['id'] == opcion['id']), None)
        if existente is None:
            existente = dict(opcion, puntuacion=0, coincidencias=[], pistas_nombre=[], requiere_revision=True)
            encontradas.append(existente)
        existente['puntuacion'] += 12 * evidencia['puntuacion']
        existente['fuente'] = 'clasificador_supervisado_de_intenciones'
        existente['aprendizaje_supervisado'] = evidencia
    encontradas.sort(key=lambda o: (-o['puntuacion'], o['requiere_revision'], o['id']))
    return encontradas[:limite]


def contexto_candidatas(consulta):
    candidatas = buscar_animaciones(consulta)
    if not candidatas:
        return ''
    return ('\nCANDIDATAS DE BUSQUEDA LOCAL PARA ESTA ESCENA. Combinan pistas léxicas y un clasificador '
            'supervisado de intenciones entrenado con frases etiquetadas. Son hipótesis, no confirmaciones visuales; '
            'evalua tambien las otras opciones. No copies una candidata sin comprobar que encaja.\n'
            + json.dumps(candidatas, ensure_ascii=False, separators=(',', ':')))
