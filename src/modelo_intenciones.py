"""Inferencia del clasificador supervisado exportado; no necesita sklearn ni pickle.

El vocabulario, IDF, coeficientes e interceptos se aprenden en entrenar_intenciones.py.
Las restricciones de alcance son guardas del compilador, no etiquetas aprendidas.
"""
from collections import Counter
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata

from src.paths import RESOURCE_ROOT

CARPETA_MODELO = RESOURCE_ROOT / 'models/intenciones'
VERSION_CARACTERISTICAS = 1
OMITIR = set('''a al ante bajo con de del desde durante el ella ellos en entre es esta
este haga hace hacer hay la las le les lo los me mi para personaje personajes persona
personas por que quiero se su sus un una uno unos unas dos tres cuatro escena segundos
segundo minuto minutos gta san andreas ciudad campo playa desierto noche atardecer
policia policias granjero granjeros actor actores hombre hombres mujer mujeres'''.split())


def normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto).lower())
                   if not unicodedata.combining(c))


def caracteristicas(texto):
    """Misma extracción para entrenamiento e inferencia; sin listas de sinónimos."""
    tokens = [t for t in re.findall(r'[a-z]+', normalizar(texto)) if t not in OMITIR]
    resultado = Counter('w:' + t for t in tokens)
    resultado.update('b:' + a + ' ' + b for a, b in zip(tokens, tokens[1:]))
    for token in tokens:
        palabra = ' ' + token + ' '
        for n in (3, 4, 5):
            resultado.update(f'c{n}:' + palabra[i:i+n] for i in range(len(palabra)-n+1))
    return dict(resultado)


def firma_modelo():
    return tuple((p.stat().st_mtime_ns, p.stat().st_size) if p.exists() else (0, 0)
                 for p in (CARPETA_MODELO / 'metadata.json', CARPETA_MODELO / 'pesos.npz'))


def _cargar(firma):
    return _cargar_ruta(str(CARPETA_MODELO.resolve()), firma)


@lru_cache(maxsize=2)
def _cargar_ruta(carpeta, firma):
    import numpy as np
    if not all(f[0] for f in firma):
        return None
    carpeta = Path(carpeta)
    metadata = json.loads((carpeta / 'metadata.json').read_text(encoding='utf-8'))
    if metadata.get('version_caracteristicas') != VERSION_CARACTERISTICAS:
        raise ValueError('Versión de características del clasificador incompatible.')
    contenido = (carpeta / 'pesos.npz').read_bytes()
    if hashlib.sha256(contenido).hexdigest() != metadata['sha256_pesos']:
        raise ValueError('Los pesos del clasificador no corresponden a sus metadatos.')
    with np.load(carpeta / 'pesos.npz', allow_pickle=False) as archivo:
        idf = archivo['idf'].astype(float)
        coef = archivo['coef'].astype(float)
        intercept = archivo['intercept'].astype(float)
    if (idf.shape != (len(metadata['vocabulario']),) or
            coef.shape != (len(metadata['clases']), len(idf)) or
            intercept.shape != (len(metadata['clases']),) or
            not all(np.isfinite(a).all() for a in (idf, coef, intercept))):
        raise ValueError('Dimensiones o valores de los pesos inválidos.')
    return metadata, idf, coef, intercept


def puntuaciones(texto, modelo):
    """TF sublineal, IDF aprendido, normalización L2 y softmax multiclase."""
    import numpy as np
    metadata, idf, coef, intercept = modelo
    rasgos = caracteristicas(texto)
    entradas = [(metadata['vocabulario'][k], v) for k, v in rasgos.items()
                if k in metadata['vocabulario']]
    if not entradas:
        return None, 0.0
    indices = np.array([i for i, _ in entradas])
    valores = np.array([1 + math.log(v) for _, v in entradas]) * idf[indices]
    valores /= np.linalg.norm(valores)
    logits = coef[:, indices] @ valores + intercept
    probabilidades = np.exp(logits - logits.max())
    probabilidades /= probabilidades.sum()
    cobertura = len(entradas) / max(1, len(rasgos))
    return probabilidades, cobertura


def motivo_abstencion(texto):
    """Este modelo interpreta un gesto; las otras mecánicas tienen su propia vía."""
    t = normalizar(texto)
    if len(t.strip()) < 4 or len(t) > 500:
        return 'longitud_fuera_de_alcance'
    if re.search(r'\b(no|sin|nunca|jamas|tampoco|ni)\b', t):
        return 'negacion'
    if re.search(r'\b(luego|despues|finalmente|mientras|simultaneamente)\b|[;\n]|\by\b', t):
        return 'varias_acciones_o_relaciones'
    if re.search(r'\b(camin\w*|corr\w*|trot\w*|nad(?:ar|a|an|ando)|salt\w*|apunt\w*|'
                 r'escaleras?|conduc\w*|manej\w*|auto|carro|coche|vehiculo|taxi|moto|bus|'
                 r'techo|encima|dispar\w*|pele\w*|golpe\w*|volar|vuel\w*|dragon\w*|'
                 r'teletransport\w*|explosi\w*|mat\w*|asesin\w*)\b', t):
        return 'mecanica_fuera_del_clasificador_de_gestos'
    return ''


def predecir_intencion(texto):
    """Una puntuación softmax no es una garantía de corrección ni de resultado visual."""
    return dict(_predecir(str(texto), str(CARPETA_MODELO.resolve()), firma_modelo()))


@lru_cache(maxsize=512)
def _predecir(texto, carpeta, firma):
    motivo = motivo_abstencion(texto)
    if motivo:
        return dict(aceptada=False, motivo=motivo)
    try:
        modelo = _cargar_ruta(carpeta, firma)
    except (OSError, ValueError, KeyError, ImportError):
        return dict(aceptada=False, motivo='modelo_no_disponible_o_incompatible')
    if modelo is None:
        return dict(aceptada=False, motivo='modelo_no_entrenado')
    metadata = modelo[0]
    probabilidades, cobertura = puntuaciones(texto, modelo)
    if probabilidades is None:
        return dict(aceptada=False, motivo='sin_vocabulario_conocido')
    indices = probabilidades.argsort()[::-1]
    primero = int(indices[0])
    puntuacion = float(probabilidades[primero])
    margen = puntuacion - float(probabilidades[indices[1]])
    intencion = metadata['clases'][primero]
    aceptada = (intencion != 'desconocido' and puntuacion >= metadata['umbral'] and
                margen >= metadata['margen_minimo'] and cobertura >= metadata['cobertura_minima'])
    return dict(aceptada=aceptada, intencion=intencion, puntuacion=round(puntuacion, 6),
                margen=round(margen, 6), cobertura_vocabulario=round(cobertura, 6),
                umbral=metadata['umbral'], modelo=metadata['id_modelo'],
                sha256_pesos=metadata['sha256_pesos'],
                motivo='clasificacion_supervisada' if aceptada else 'abstencion_por_incertidumbre')
