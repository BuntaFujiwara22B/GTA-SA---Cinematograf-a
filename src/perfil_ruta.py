"""Perfiles de superficie: una imagen de alturas no distingue suelo y estructuras."""
import math
from src.paths import ASSETS
from src.datos_cache import leer_json


def puente_coincidente(inicio,destino):
    archivo=ASSETS/'lugares_semanticos.json'
    if not archivo.exists():return None
    for ruta in leer_json(archivo).get('rutas',[]):
        if 'puente' not in ruta.get('etiquetas',[]):continue
        a,b=ruta['inicio'],ruta['destino'];dx,dy=b[0]-a[0],b[1]-a[1];l2=dx*dx+dy*dy
        if not l2:continue
        coincide=True
        for p in (inicio,destino):
            t=((p[0]-a[0])*dx+(p[1]-a[1])*dy)/l2
            proy=(a[0]+t*dx,a[1]+t*dy,a[2]+t*(b[2]-a[2]))
            if not -.02<=t<=1.02 or math.dist(p[:2],proy[:2])>1.2 or abs(p[2]-proy[2])>1.2:
                coincide=False;break
        if coincide:return ruta
    return None


def error_pendiente(inicio,destino,tipo='caminar',superficie=None):
    d=math.dist(inicio[:2],destino[:2])
    limite=.25 if superficie=='puente' else 1.15 if tipo=='escaleras' else .75
    if d<.01 or abs(destino[2]-inicio[2])/d>limite:
        return ('El recorrido del puente tiene una pendiente excesiva. Cambia los puntos.' if superficie=='puente'
            else 'El recorrido tiene una pendiente excesiva o un corte vertical. Cambia los puntos.')
    return ''


def interpolar(puntos,f):
    longitudes=[math.dist(a[:2],b[:2]) for a,b in zip(puntos,puntos[1:])]
    restante=sum(longitudes)*max(0,min(1,f))
    for a,b,l in zip(puntos,puntos[1:],longitudes):
        if restante<=l or b==puntos[-1]:
            t=min(1,restante/l) if l else 0
            return tuple(v+(w-v)*t for v,w in zip(a,b))
        restante-=l
    return tuple(puntos[-1])


def recortar(puntos,desde,hasta):
    total=sum(math.dist(a[:2],b[:2]) for a,b in zip(puntos,puntos[1:]))
    resultado=[interpolar(puntos,desde)];recorrido=0
    for a,b in zip(puntos,puntos[1:]):
        recorrido+=math.dist(a[:2],b[:2])
        if desde<recorrido/total<hasta:resultado.append(tuple(b))
    fin=interpolar(puntos,hasta)
    if math.dist(resultado[-1],fin)>.001:resultado.append(fin)
    return resultado


def validar_perfil(puntos,inicio,destino,tipo='caminar'):
    if not isinstance(puntos,(list,tuple)) or not 2<=len(puntos)<=100:
        raise ValueError('El perfil del recorrido está incompleto.')
    if any(len(p)!=3 or not all(isinstance(v,(float,int)) and math.isfinite(v) for v in p) or
        abs(p[0])>3000 or abs(p[1])>3000 or not -100<=p[2]<=2000 for p in puntos):
        raise ValueError('El perfil contiene coordenadas no válidas.')
    if math.dist(puntos[0],inicio)>.1 or math.dist(puntos[-1],destino)>.1:
        raise ValueError('El perfil corresponde a otro recorrido; vuelve a comprobarlo.')
    superficie='puente' if puente_coincidente(inicio,destino) else None
    dx,dy=destino[0]-inicio[0],destino[1]-inicio[1];l2=dx*dx+dy*dy
    anterior=-.001
    for p in puntos:
        t=((p[0]-inicio[0])*dx+(p[1]-inicio[1])*dy)/l2 if l2 else -1
        if not anterior<t<=1.001 or math.dist(p[:2],(inicio[0]+t*dx,inicio[1]+t*dy))>.2:
            raise ValueError('El perfil se sale del recorrido o retrocede.')
        anterior=t
    for a,b in zip(puntos,puntos[1:]):
        error=error_pendiente(a,b,tipo,superficie)
        if error:raise ValueError(error)
    return [tuple(p) for p in puntos]


def campos_waypoints(puntos,tipo,orientacion):
    campos={'POINT_TOTAL':str(len(puntos))}
    for n,p in enumerate(puntos,1):
        campos.update({f'POINT_X{n}':str(p[0]),f'POINT_Y{n}':str(p[1]),
            f'POINT_Z{n}':str(p[2]+(0 if tipo=='nadar' else 1)),f'POINT_A{n}':str(orientacion),
            f'POINT_MODE{n}':'2' if tipo=='correr' else '1',f'POINT_JUMP{n}':'0'})
    return campos
