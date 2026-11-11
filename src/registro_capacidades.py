"""Conocimiento compartido por el planificador, los indicadores y el compilador.

Un clip existente no demuestra que estén implementados sus objetos, soportes o efectos.
"""
import json
import re
from src.paths import ASSETS
from src.datos_cache import leer_json
from src.escenas_semanticas import normalizar


def soportes_vehiculos():
    return leer_json(ASSETS/'soportes_vehiculos.json')['vehiculos']


def pide_techo_vehiculo(texto):
    t=normalizar(texto)
    from src.catalogos_entidades import disponibles
    nombres={normalizar(v['nombre']) for v in [*disponibles('vehicles'),*soportes_vehiculos()]}
    nombres.update(('auto','carro','coche','vehiculo','taxi','moto','motocicleta','bicicleta','bus','autobus'))
    vehiculo='(?:'+'|'.join(re.escape(n) for n in sorted(nombres,key=len,reverse=True))+')'
    articulo=r'(?:(?:un|el|ese|su|una|la)\s+)?'
    techo=r'techo\s+(?:del|de)\s*'+articulo
    soporte=r'(?:'+techo+r'|(?:sobre|encima(?:\s+del?)?)\s+'+articulo+r'(?:'+techo+r')?)'
    if re.search(r'\b'+soporte+vehiculo+r'\b',t):return True
    # Referencia anafórica: «un coche con alguien fumando en el techo».
    return bool(re.search(r'\b'+vehiculo+r'\b',t) and re.search(r'\b(?:en|sobre)\s+(?:su|el)\s+techo\b(?!\s+(?:de|del)\b)',t))


def pide_vehiculo_movil(texto):
    t=normalizar(texto)
    if re.search(r'\b(?:estacionad\w*|aparcad\w*|quieto|detenido|sin moverse|no se mueve|sin movimiento)\b',t):return False
    return bool(re.search(r'\b(?:en movimiento|de movimiento|moviend\w*|conduc\w*|manej\w*|circul\w*|avanz\w*|recorr\w*|anda|mueve|mueva)\b',t))


def registro():
    from src.capacidades_escena import FAMILIAS,opciones
    familias=[]
    for titulo,_,categoria,nombre in FAMILIAS:
        clips=[o['id'] for o in opciones() if (categoria is None or o['categoria']==categoria) and re.search(nombre,o['anim'],re.I)]
        familias.append(dict(accion=titulo,clips=clips,estado='clip_exportable',
            alcance='Reproduce el gesto; no crea automáticamente objetos, humo ni efectos.'))
    return dict(version=1,clips_exportables=len(opciones()),familias=familias,
        composiciones=[
            dict(id='secuencia',estado='implementada',limites='1..8 tareas consecutivas, 1..4 actores, 1..60 segundos'),
            dict(id='conducir_vehiculo',estado='implementada',limites='Entrar, esperar entrada real y conducir con CARREC'),
            dict(id='animacion_sobre_vehiculo',estado='experimental_exportable',
                limites='Un actor comienza anclado al techo, uno o varios clips consecutivos y vehículo parado o en ruta. No representa subir, bajar, caminar ni saltar desde el techo.',
                modelos=[s['model_id'] for s in soportes_vehiculos()],
                evidencia='EntityCreate: Type=2/SPHERE_TYPE=6 sujeta el actor. Animación Type=3/SPHERE_TYPE=0/TP=0 conserva el anclaje. ACTION_A se carga antes que ACTION_V.',
                pendiente='Comprobar en GTA posición, pies y persistencia del anclaje al reproducir cada clip.')],
        pendientes=['Animar al conductor mientras conduce','Acciones distintas simultáneas no vinculadas a un soporte',
            'Combate real','Objetos en la mano y efectos de humo automáticos','Alineación automática con cualquier silla o cama'],
        reglas='Si existe el clip pero falta una composición, identifica la parte pendiente; no declares imposible la acción en el mod.')


def contexto_capacidades(texto='',compacto=False):
    datos=registro()
    if compacto:datos=dict(datos,familias=[f['accion'] for f in datos['familias']])
    return '\nREGISTRO DE CAPACIDADES DEL COMPILADOR (autoridad sobre su alcance, datos no instrucciones):\n'+json.dumps(datos,ensure_ascii=False)


def diagnostico(texto):
    from src.capacidades_escena import candidata_local
    t=normalizar(texto);c=candidata_local(t)
    if c:
        pendiente=requisitos_pendientes(texto)
        falta=' '.join(pendiente) if pendiente else 'Falta resolver la combinación con los otros movimientos, participantes o el soporte pedido.'
        return f'La animación para {c[0]} sí existe ({c[1]["anim"]}). {falta} No se exportará solo el gesto omitiendo el resto.'
    return 'No se confirmó una composición exportable para toda la petición. El catálogo puede contener la animación, pero también hay que resolver participantes, objetos, soporte y movimiento.'


def requisitos_pendientes(texto):
    t=normalizar(texto);pendientes=[]
    if re.search(r'\b(?:sentad\w*|sient\w*|sentar\w*)\b',t) and re.search(r'\b(?:silla|sillon|banco|sofa)\b',t):
        pendientes.append('La colocación y alineación del personaje con ese asiento todavía no está implementada.')
    if re.search(r'\b(?:tumb\w*|acost\w*|duerm\w*|dormir)\b',t) and re.search(r'\b(?:cama|camilla|sofa)\b',t):
        pendientes.append('Falta colocar y alinear al personaje sobre ese mueble.')
    if re.search(r'\b(?:humo|ceniza|cigarrillo visible|cigarrillo en la mano)\b',t):
        pendientes.append('Los objetos en la mano y los efectos de humo aún no se crean automáticamente.')
    return pendientes
