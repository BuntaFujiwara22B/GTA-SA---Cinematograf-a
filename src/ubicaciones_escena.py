"""Ubicaciones y recorridos basados en nodos reales del GTA instalado."""
import math
import random
from src.paths import ASSETS
from src.datos_cache import leer_json


def catalogo():
    return leer_json(ASSETS/'ubicaciones_escena.json')


def ubicaciones(entorno=None):
    extras=ASSETS/'lugares_semanticos.json'
    todos=catalogo()['ubicaciones']+(leer_json(extras)['ubicaciones'] if extras.exists() else [])
    return [p for p in todos if entorno is None or p['entorno']==entorno]


def rutas_vehiculos():
    return catalogo()['rutas_vehiculos']


def zona_pedida(texto):
    t=texto.lower()
    return next((z for z in ('San Fierro','Las Venturas','Los Santos') if z.lower() in t),None)


def elegir_ubicacion(entorno,texto='',rng=None):
    candidatas=ubicaciones(entorno)
    if 'puente' in texto.lower():candidatas=[p for p in candidatas if 'puente' in p.get('etiquetas',[])]
    zona=zona_pedida(texto)
    if zona:candidatas=[p for p in candidatas if p['zona']==zona]
    if not candidatas:raise ValueError('No hay ubicaciones predeterminadas para esa zona. Marca el lugar en el mapa.')
    return (rng or random.SystemRandom()).choice(candidatas)


def elegir_ruta_vehiculo(texto='',identificador=None,rng=None):
    todas=rutas_vehiculos();candidatas=todas
    zona=zona_pedida(texto)
    if zona:candidatas=[p for p in candidatas if p['zona']==zona]
    t=texto.lower().replace('cuidad','ciudad')
    entorno=next((e for e in ('campo','desierto') if e in t),None)
    if not entorno and any(p in t for p in ('ciudad','calle','avenida')):entorno='ciudad'
    if entorno:candidatas=[p for p in candidatas if p.get('entorno')==entorno]
    if not candidatas:raise ValueError('No hay rutas disponibles en esa zona.')
    if identificador:
        ruta=next((p for p in candidatas if p['id']==identificador),None)
        if ruta:return ruta
        if not any(p['id']==identificador for p in todas):raise ValueError('La ruta del vehículo no pertenece al catálogo.')
    return (rng or random.SystemRandom()).choice(candidatas)


def puntos_entrada(ruta):
    a,b=ruta['puntos'][:2]
    dx,dy=b[0]-a[0],b[1]-a[1]
    d=math.hypot(dx,dy)
    # Puerta del conductor, a una distancia corta para que pueda entrar.
    return (a[0]-dy/d*3.5-dx/d*1.5,a[1]+dx/d*3.5-dy/d*1.5,a[2]),tuple(a)


def contexto_ubicaciones(texto=''):
    import hashlib,json
    semilla=int(hashlib.sha256(texto.encode('utf-8')).hexdigest()[:8],16)
    rng=random.Random(semilla)
    t=texto.lower()
    entorno=next((e for e in ('campo','desierto','playa') if e in t),'ciudad')
    lugares=ubicaciones(entorno)
    if 'puente' in t:lugares=[u for u in lugares if 'puente' in u.get('etiquetas',[])]
    zona=zona_pedida(texto)
    if zona:lugares=[u for u in lugares if u['zona']==zona]
    lugares=rng.sample(lugares,min(16,len(lugares)))
    return ('\nUBICACIONES: hay '+str(len(ubicaciones()))+' ubicaciones del catálogo por entorno. '
        'Elige ubicacion_id_sugerida para una animación estática de estas candidatas: '+json.dumps(lugares,ensure_ascii=False)+
        '\nLa interfaz conserva tu propuesta y el usuario puede cambiarla. '
        'CONDUCCIÓN: rutas nativas predefinidas; usa accion=conducir_vehiculo para subir y conducir. '
        'Una persona, vehículo del catálogo, ruta_vehiculo_id opcional. '
        'No inventes coordenadas ni asegures colisiones comprobadas.\n'+
        '\n'.join(f"{r['id']}: {r['nombre']} ({r['zona']}, {r.get('entorno','ciudad')}, {r['longitud']} m)" for r in rutas_vehiculos()))
