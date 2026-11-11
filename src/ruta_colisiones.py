from src.paths import DATA_ROOT
"""Puente de comprobacion con GTA; una ausencia de respuesta nunca significa ruta libre."""
import asyncio
import json
import math
import time
from pathlib import Path
from uuid import uuid4

CARPETA = DATA_ROOT / 'ruta_mvp'


def sugerir_ruta(entorno, duracion, obtener_z, ruta_id=None):
    """Propone puntos usando alturas; no acredita ausencia de colisiones."""
    from src.mvp_mms import POS_INICIO, POS_DESTINO
    if entorno == 'ciudad':
        from src.calles_escena import rutas_disponibles, elegir_calle
        elegida=next((r for r in rutas_disponibles() if r['id']==ruta_id),None) or elegir_calle('',duracion)
        if elegida:
            from src.perfil_ruta import puente_coincidente
            if puente_coincidente(elegida['inicio'],elegida['destino']):
                return tuple(elegida['inicio']),tuple(elegida['destino'])
            puntos=[]
            for x,y,z_nodo in (elegida['inicio'],elegida['destino']):
                z=obtener_z(x,y)
                if not math.isfinite(z) or abs(z-z_nodo)>3:
                    raise ValueError('La altura del mapa no coincide con la ruta peatonal propuesta. Marca otra ubicación o comprueba la ruta en GTA.')
                puntos.append((x,y,z))
            return tuple(puntos)
        return POS_INICIO, POS_DESTINO
    # Retirar (200,-100): la prueba del usuario mostro viviendas en esa zona.
    semillas = {'campo': (-450.0,-450.0), 'desierto': (-200.0,2500.0), 'playa': (380.0,-2000.0)}
    x,y = semillas.get(entorno,semillas['campo'])
    z = obtener_z(x,y)
    if not math.isfinite(z):
        raise ValueError('No se pudo leer la altura para sugerir una ruta.')
    distancia = max(12,min(60,float(duracion)*1.2))
    candidatas=[]
    for longitud in (distancia,12):
        for angulo in range(0,360,45):
            dx,dy=math.cos(math.radians(angulo))*longitud,math.sin(math.radians(angulo))*longitud
            alturas=[obtener_z(x+dx*i/12,y+dy*i/12) for i in range(13)]
            if not all(math.isfinite(a) and a>0.5 for a in alturas):
                continue
            salto=max(abs(b-a) for a,b in zip(alturas,alturas[1:]))
            from src.perfil_ruta import error_pendiente
            if any(error_pendiente((x+dx*i/12,y+dy*i/12,alturas[i]),
                (x+dx*(i+1)/12,y+dy*(i+1)/12,alturas[i+1])) for i in range(12)):
                continue
            candidato=(x+dx,y+dy,alturas[-1])
            if revisar_superficie_elevada((x,y,z),candidato,obtener_z):
                continue
            puntuacion=salto + (0.1 if longitud<distancia else 0)
            candidatas.append((puntuacion,(x+dx,y+dy,alturas[-1])))
    if not candidatas:
        raise ValueError('No encontré un recorrido con alturas adecuadas en la zona sugerida. Marca los puntos en el mapa.')
    _,destino=min(candidatas,key=lambda c:c[0])
    return (x,y,z),destino


async def comprobar_en_gta(inicio, destino, timeout=35):
    if len(inicio)!=3 or len(destino)!=3 or not all(math.isfinite(v) for v in (*inicio,*destino)):
        return dict(estado='error',mensaje='Las coordenadas de la ruta no son validas.')
    CARPETA.mkdir(exist_ok=True)
    identificador=uuid4().hex
    temporal=CARPETA/'solicitud.tmp'
    temporal.write_text(','.join([identificador]+[f'{v:.6f}' for v in (*inicio,*destino)]),encoding='ascii')
    temporal.replace(CARPETA/'solicitud.txt')
    limite=time.monotonic()+timeout
    while time.monotonic()<limite:
        try:
            respuesta=json.loads((CARPETA/'respuesta.json').read_text(encoding='utf-8'))
            if respuesta.get('id')==identificador:
                return respuesta
        except (OSError,ValueError):
            pass
        await asyncio.sleep(.2)
    return dict(estado='sin_comprobar',mensaje='La ruta sigue sin comprobar. GTA puede estar pausado al cambiar de ventana: pulsa comprobar y vuelve a GTA durante unos segundos, con la partida activa y el jugador cerca de la ruta.')


def evaluar_perfil(inicio,destino,obtener_z,tipo='caminar',superficie=None):
    """Separar discontinuidad, pendiente transitable y mapa 2D ambiguo."""
    from src.perfil_ruta import puente_coincidente,error_pendiente
    distancia=math.dist(inicio[:2],destino[:2])
    puente=puente_coincidente(inicio,destino)
    superficie='puente' if puente else superficie
    error=error_pendiente(inicio,destino,tipo,superficie)
    if error:return dict(estado='bloqueada',mensaje=error,puntos=[])
    n=max(2,min(100,math.ceil(distancia/2)))
    puntos=[]
    for i in range(n+1):
        t=i/n
        x,y=inicio[0]+t*(destino[0]-inicio[0]),inicio[1]+t*(destino[1]-inicio[1])
        z=obtener_z(x,y)
        if not math.isfinite(z):
            return dict(estado='bloqueada',mensaje='No se pudo leer la altura del terreno.',puntos=[])
        puntos.append((x,y,inicio[2]+t*(destino[2]-inicio[2]) if puente else z))
    if puente:
        return dict(estado='incierto',fuente=puente['id'],puntos=puntos,
            mensaje='Se conserva la altura del puente de referencia. El mapa 2D puede mostrar estructuras a otra altura; faltan comprobar superficie y obstáculos en GTA.')
    for a,b in zip(puntos,puntos[1:]):
        error=error_pendiente(a,b,tipo,superficie)
        if error:return dict(estado='bloqueada',mensaje='Hay un cambio brusco de altura o una pendiente excesiva en el recorrido. Revisa la ubicación antes de generar.',puntos=[])
    error=revisar_superficie_elevada(inicio,destino,obtener_z)
    if error:return dict(estado='bloqueada',mensaje=error,puntos=[])
    if abs(puntos[0][2]-inicio[2])>3 or abs(puntos[-1][2]-destino[2])>3:
        return dict(estado='bloqueada',mensaje='La altura elegida no coincide con la superficie del mapa. Marca otra vez los puntos o comprueba la superficie en GTA.',puntos=[])
    puntos[0],puntos[-1]=tuple(inicio),tuple(destino)
    try:
        from src.perfil_ruta import validar_perfil
        validar_perfil(puntos,inicio,destino,tipo)
    except ValueError as e:return dict(estado='bloqueada',mensaje=str(e),puntos=[])
    return dict(estado='apto',mensaje='',puntos=puntos,fuente='mapa_alturas')


def revisar_desniveles(inicio,destino,obtener_z,**opciones):
    resultado=evaluar_perfil(inicio,destino,obtener_z,**opciones)
    return resultado['mensaje'] if resultado['estado']=='bloqueada' else ''


def revisar_superficie_elevada(inicio,destino,obtener_z):
    """Heuristica de tejados/bordes: la altura central supera el terreno vecino."""
    n=max(1,min(40,math.ceil(math.dist(inicio[:2],destino[:2])/4)))
    for i in range(n+1):
        t=i/n
        x,y=inicio[0]+t*(destino[0]-inicio[0]),inicio[1]+t*(destino[1]-inicio[1])
        centro=obtener_z(x,y)
        offsets=[(8*math.cos(math.radians(a)),8*math.sin(math.radians(a))) for a in range(0,360,45)]
        vecinas=[obtener_z(x+dx,y+dy) for dx,dy in offsets]
        if not all(math.isfinite(z) for z in [centro,*vecinas]):
            return 'No se pudo comprobar la superficie del recorrido.'
        gx=(vecinas[0]-vecinas[4])/16;gy=(vecinas[2]-vecinas[6])/16
        if sum(centro-(z-gx*dx-gy*dy)>2.5 for z,(dx,dy) in zip(vecinas,offsets))>=3:
            return 'El recorrido parece estar sobre una superficie elevada o junto a un desnivel. Cambia la ubicación; podría ser un tejado.'
    return ''
