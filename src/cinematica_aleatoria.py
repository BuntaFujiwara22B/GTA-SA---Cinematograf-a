"""Propuestas locales con acciones consecutivas y recursos reales del catálogo."""
import random
from functools import lru_cache

from src.mvp_plan import plan_local
from src.calles_escena import rutas_disponibles
from src.catalogos_entidades import disponibles
from src.ubicaciones_escena import ubicaciones, rutas_vehiculos


# Cada guion usa tareas que el compilador ya sabe programar por objetivos.
# No se combinan dos clips simultáneos ni se inventan combate, humo u objetos.
_GUIONES = (
    ('Encuentro en la ciudad', (('camina', 'caminan'), ('saluda', 'saludan'),
        ('habla', 'hablan')), True),
    ('Una pequeña celebración', (('saluda', 'saludan'), ('baila', 'bailan'),
        ('aplaude', 'aplauden')), False),
    ('Paseo con una pausa', (('camina', 'caminan'), ('saluda', 'saludan')), True),
    ('Ensayo de baile', (('baila', 'bailan'), ('aplaude', 'aplauden'),
        ('saluda', 'saludan')), False),
    ('Reunión al aire libre', (('habla', 'hablan'), ('saluda', 'saludan'),
        ('aplaude', 'aplauden')), False),
    ('Llegada a la plaza', (('saluda', 'saludan'), ('camina', 'caminan'),
        ('aplaude', 'aplauden')), True),
)
_HORAS = ((6, 'al amanecer'), (12, 'al mediodía'), (18, 'al atardecer'),
    (22, 'de noche'))
_CLIMAS = {
    'Los Santos': (0, 1, 4), 'San Fierro': (5, 6, 7, 9),
    'Las Venturas': (10, 11, 12), 'campo': (13, 14, 15),
    'desierto': (17, 18), 'playa': (0, 1, 4),
}
_NUBLADOS = {4, 7, 12, 15}
_CAMARAS = ('Tercera Persona', 'Seguimiento lateral', 'Cámara Fija Cinematográfica')


@lru_cache(maxsize=1)
def _alturas():
    from visor_mapa import GestorAlturas
    return GestorAlturas()


@lru_cache(maxsize=128)
def _perfil_peatonal_apto(inicio, destino):
    """Descarta nodos incompatibles con el terreno; no comprueba colisiones."""
    import math
    from src.ruta_colisiones import evaluar_perfil
    if not 2 <= math.dist(inicio[:2], destino[:2]) <= 150:
        return False
    obtener_z = _alturas().obtener_z
    puntos = [tuple(p[:2]) + (obtener_z(*p[:2]),) for p in (inicio, destino)]
    if any(not math.isfinite(p[2]) or abs(p[2] - nodo[2]) > 3
            for p, nodo in zip(puntos, (inicio, destino))):
        return False
    return evaluar_perfil(*puntos, obtener_z)['estado'] == 'apto'


def _ambiente(rng, entorno, zona):
    hora, momento = rng.choice(_HORAS)
    clima = rng.choice(_CLIMAS.get(entorno if entorno != 'ciudad' else zona, (0, 1, 4)))
    cielo = 'con niebla' if clima == 9 else 'con cielo nublado' if clima in _NUBLADOS else 'con cielo despejado'
    return hora, clima, f'{momento}, {cielo}'


def crear_escena_aleatoria(actores, rng=None):
    """Devuelve un plan editable completo; ``rng`` controla todas las elecciones.

    Mezcla escenas de dos o tres tareas con entrada y conducción de vehículos.
    Las rutas del catálogo son propuestas: no acreditan colisiones comprobadas.
    """
    rng = rng or random.SystemRandom()
    actores = list(dict.fromkeys(actores))
    if not actores:
        raise ValueError('No hay personajes disponibles.')

    calles = [r for r in rutas_disponibles()
        if _perfil_peatonal_apto(tuple(r['inicio']), tuple(r['destino']))]
    lugares = ubicaciones()
    recorridos = rutas_vehiculos()
    # Coches con los que ya funciona la entrada como conductor. No elegir una
    # moto, un avión o un barco solo porque tenga foto en el catálogo.
    coches = [v for v in disponibles('vehicles') if v['model_id'] in (400, 405, 411, 420, 426, 489)]
    guiones = [g for g in _GUIONES if (calles if g[2] else lugares)]
    candidatos = guiones + ([None] if recorridos and coches else [])
    if not candidatos:
        raise ValueError('No hay ubicaciones o recorridos disponibles para crear una escena.')
    guion = rng.choice(candidatos)
    conduccion = guion is None

    if conduccion:
        titulo = 'Un viaje por San Andreas'
        lugar = rng.choice(recorridos)
        entorno = lugar.get('entorno', 'ciudad')
        cantidad = 1
        duracion = rng.choice((20, 25, 30, 35))
        coche = rng.choice(coches)
        velocidad = rng.choice((25, 30, 35, 40, 45))
        acciones = f'se sube a un auto {coche["nombre"]} y conduce a {velocidad} km/h'
    else:
        titulo, verbos, movimiento = guion
        cantidad = rng.randint(1, min(4, len(actores)))
        duracion = rng.choice((24, 28, 32, 36))
        lugar = rng.choice(calles if movimiento else lugares)
        entorno = 'ciudad' if movimiento else lugar['entorno']
        frases = [v[0 if cantidad == 1 else 1] for v in verbos]
        acciones = ', luego '.join(frases[:-1]) + ' y finalmente ' + frases[-1]

    zona = lugar.get('zona', 'Los Santos')
    hora, clima, ambiente = _ambiente(rng, entorno, zona)
    lugar_texto = f'en la ciudad de {zona}' if entorno == 'ciudad' else f'en el {entorno}' if entorno != 'playa' else 'en la playa'
    sujeto = 'Un personaje' if cantidad == 1 else f'{cantidad} personajes'
    texto = f'{sujeto} {acciones} {lugar_texto} {ambiente}, durante {duracion} segundos en total.'
    plan = plan_local(texto)
    if not plan.es_valido:
        raise ValueError(f'No se pudo preparar la escena aleatoria: {plan.razon_rechazo}')
    reparto = rng.sample(actores, cantidad)
    plan.fuente = 'Generador aleatorio local'
    plan.resumen = f'{titulo}: {acciones}.'
    plan.actor_id_sugerido = reparto[0]
    plan.actores_ids_sugeridos = reparto[:]
    plan.hora_sugerida = hora
    plan.clima_id_sugerido = clima
    plan.entorno_sugerido = entorno
    plan.motivo_elecciones = (f'{titulo}. Acciones consecutivas, reparto disponible y ambiente coherente '
        f'con {zona}. Puedes ajustar la propuesta antes de guardarla.')
    if conduccion:
        plan.ruta_vehiculo_id = lugar['id']
        plan.vehiculo_id_sugerido = coche['model_id']
        camara = 'Tercera Persona'
    elif movimiento:
        plan.ruta_id_sugerida = lugar['id']
        camara = rng.choice(_CAMARAS)
    else:
        plan.ubicacion_id_sugerida = lugar['id']
        plan.ruta_id_sugerida = None
        # Un encuadre fijo presenta mejor un grupo que permanece en un lugar.
        camara = rng.choice(('Seguimiento lateral', 'Cámara Fija Cinematográfica'))
    return dict(texto=texto, plan=plan, actores=reparto, camara=camara,
        titulo=titulo, ambiente=ambiente,
        categoria_musica='feliz' if any(p.accion == 'animacion' and p.reproduccion == 'bucle' for p in plan.pasos)
            and hora != 22 else 'mistica')
