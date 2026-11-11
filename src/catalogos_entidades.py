from src.paths import RESOURCE_ROOT
from src.datos_cache import leer_json
import json
from pathlib import Path

ROOT=RESOURCE_ROOT


def catalogo(tipo):
    if tipo not in ('vehicles','objects'):raise ValueError('Catálogo desconocido.')
    p=ROOT/'assets'/f'{tipo}_catalogo.json'
    return leer_json(p) if p.exists() else []


def disponibles(tipo):
    return [o for o in catalogo(tipo) if o['disponible'] and (ROOT/'assets'/o['foto']).is_file()]


def contexto_entidades():
    return ('\nVEHICULOS Y OBJETOS REALES DEL USUARIO. model_id es el valor de Model en el MMS, '
        'nunca el numero de captura. Nombres e IDs confirmados por su tabla; fotos disponibles, no descripciones visuales inferidas. '
        'Entrar a un vehiculo se exporta para un actor. Si después conduce, usa conducir_vehiculo con una ruta del catálogo. '
        'Los objetos estan catalogados para consulta; sentarse en una silla necesita implementar y validar su alineacion y colocacion. '
        'No afirmar que una funcion pendiente del generador sea imposible en el mod.\n'
        +json.dumps({t:catalogo(t) for t in ('vehicles','objects')},ensure_ascii=False))


def fotos_entidades(texto):
    t=texto.lower()
    objetos=disponibles('objects');vehiculos=disponibles('vehicles')
    if 'silla' in t:return [o for o in objetos if o['model_id'] in (1704,1714)][:2]
    exactas=[o for o in vehiculos if o['nombre'].lower() in t]
    if exactas:return exactas[:2]
    if any(p in t for p in ('auto','carro','vehiculo','vehículo','coche')):
        return [o for o in vehiculos if o['model_id'] in (420,411)][:2]
    return []
