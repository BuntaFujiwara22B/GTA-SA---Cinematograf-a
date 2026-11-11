"""Conserva el estilo elegido y ajusta distancia y objetivo al reparto y recorrido."""
import math


def giro_frontal(config,inicio,orientacion,cantidad,duracion):
    """Desplazamiento corto por delante del actor con transición nativa (modo 1)."""
    rad=math.radians(orientacion)
    frente=(-math.sin(rad),math.cos(rad));lado=(math.cos(rad),math.sin(rad))
    distancia=4.5+cantidad*.65
    objetivo=(inicio[0],inicio[1],inicio[2]+1.1)
    objetivos=[s for s in config if s.startswith('OBJ_') and (s=='OBJ_0' or config[s].get('Type')=='6')]
    for i,s in enumerate(objetivos):
        d=config[s]
        lateral=(-.35 if i==0 else .35)*distancia
        cam=(inicio[0]+frente[0]*distancia+lado[0]*lateral,
            inicio[1]+frente[1]*distancia+lado[1]*lateral,inicio[2]+1.8)
        for k in list(d):
            if k.startswith('PLA_CUM') or k in ('CUM_ACTOR','CUM_VEH'):del d[k]
        for claves,p in [(('PLA_CUM_X','PLA_CUM_Y','PLA_CUM_Z'),cam),(('PLA_CUM_PX','PLA_CUM_PY','PLA_CUM_PZ'),objetivo)]:
            for k,v in zip(claves,p):d[k]=str(v)
        d.update(PLA_CUM='1',PLA_CUM_MODE='3' if i==0 else '1',PLA_CUM_ZOOM='60',
            PLA_CUM_TIME_MS=str(min(4000,max(1000,duracion*1000))))


def adaptar_encuadre(config,tipo,inicio,destino,orientacion,cantidad,estatica):
    rad=math.radians(orientacion)
    frente=(-math.sin(rad),math.cos(rad));lado=(math.cos(rad),math.sin(rad))
    tramo=math.dist(inicio[:2],destino[:2]) if not estatica else max(2,(cantidad-1)*1.8)
    distancia=max(7,min(65,tramo*.8+cantidad))
    centro=tuple((a+b)/2 for a,b in zip(inicio,destino)) if not estatica else (inicio[0],inicio[1]+1,inicio[2])
    objetivo=(centro[0],centro[1],centro[2]+1.1)
    if tipo=='seguimiento_trasero':
        distancia=3.2+cantidad*.45
        camara=(inicio[0]-frente[0]*distancia+lado[0]*.3,inicio[1]-frente[1]*distancia+lado[1]*.3,inicio[2]+1.25)
        objetivo=(inicio[0]+frente[0]*2,inicio[1]+frente[1]*2,inicio[2]+1.1)
    elif tipo in ('costado','seguimiento_lateral'):
        camara=(objetivo[0]+lado[0]*distancia-frente[0]*distancia*.2,
            objetivo[1]+lado[1]*distancia-frente[1]*distancia*.2,objetivo[2]+1.5)
    else:
        camara=(objetivo[0]-frente[0]*distancia+lado[0]*distancia*.35,
            objetivo[1]-frente[1]*distancia+lado[1]*distancia*.35,objetivo[2]+max(4,distancia*.5))
    dx,dy,dz=(b-a for a,b in zip(camara,objetivo))
    ax=180-math.degrees(math.atan2(dy,dx))%360
    ay=math.degrees(math.atan2(dz,math.hypot(dx,dy)))
    for seccion in config.sections():
        if not seccion.startswith('OBJ_'):continue
        d=config[seccion]
        if seccion!='OBJ_0' and d.get('Type')!='6':continue
        for claves,p in [(('PLA_CUM_X','PLA_CUM_Y','PLA_CUM_Z'),camara),(('PLA_CUM_PX','PLA_CUM_PY','PLA_CUM_PZ'),objetivo)]:
            for clave,valor in zip(claves,p):d[clave]=f'{valor:.6f}'
        d['PLA_CUM_inputX']=str(ax);d['PLA_CUM_inputY']=str(ay)
        d['PLA_CUM']='1';d['PLA_CUM_ZOOM']='70'
        for clave in list(d):
            if clave.startswith(('PLA_CUM_O','CUM_ACTOR','CUM_VEH')):del d[clave]
        d['PLA_CUM_MODE']='3'
        if seccion!='OBJ_0' and tipo=='seguimiento_trasero':
            d.update(PLA_CUM_MODE='6',CUM_ACTOR='1',PLA_CUM_OX='.3',PLA_CUM_OY=str(-distancia),PLA_CUM_OZ='1.25',
                PLA_CUM_ORX='0',PLA_CUM_ORY='0',PLA_CUM_ORZ='0')
