"""Construye un catálogo reproducible desde NODES*.DAT; no inventa lugares."""
import argparse
import json
import math
import random
import struct
from pathlib import Path
from preparar_calles import leer_nodos
from detector_entorno import detectar_entorno_gta
from visor_mapa import GestorAlturas

ROOT=Path(__file__).resolve().parent


def zona(x,y):
    return 'Los Santos' if x>400 and y<-400 else 'San Fierro' if x<-1000 and -1200<y<1600 else 'Las Venturas' if x>800 and y>500 else 'San Andreas rural'


def leer_vehiculos(carpeta):
    nodos={};enlaces={}
    for p in carpeta.glob('NODES*.DAT'):
        b=p.read_bytes()
        if len(b)<20:continue
        total,veh,peat,navi,num=struct.unpack_from('<5I',b)
        offset=20+total*28+navi*14
        if total!=veh+peat or offset+num*4>len(b):continue
        for i in range(veh):
            pos=20+i*28
            x,y,z=struct.unpack_from('<hhh',b,pos+8)
            base,area,indice=struct.unpack_from('<HHH',b,pos+16)
            flags=b[pos+24];n=flags&15
            if flags&0xA0 or b[pos+25]&8 or base+n>num:continue
            key=(area,indice);nodos[key]=(x/8,y/8,z/8)
            enlaces[key]=[struct.unpack_from('<HH',b,offset+4*(base+j)) for j in range(n)]
    return nodos,enlaces


def preparar(carpeta):
    alturas=GestorAlturas();rng=random.Random(123)
    peatonales,_=leer_nodos(carpeta)
    candidatos=list(peatonales.items());rng.shuffle(candidatos)
    sitios=[]
    cuotas={'ciudad':150,'campo':120,'desierto':80,'playa':40}
    for clave,(x,y,z_nodo) in candidatos:
        z=alturas.obtener_z(x,y)
        if not .6<z<500 or abs(z-z_nodo)>2.5:continue
        entorno=detectar_entorno_gta(x,y,z)
        if (y<-1900 and 200<x<1000) or (x<-2500 and -700<y<300):entorno='playa'
        if entorno not in cuotas or sum(p['entorno']==entorno for p in sitios)>=cuotas[entorno]:continue
        if any(math.dist((x,y),p['posicion'][:2])<35 for p in sitios):continue
        # No usar un nodo si las alturas cercanas sugieren tejados, bordes o agua.
        vecinas=[alturas.obtener_z(x+3*math.cos(a),y+3*math.sin(a)) for a in (0,math.pi/2,math.pi,math.pi*1.5)]
        if any(abs(v-z)>1.0 for v in vecinas):continue
        sitios.append(dict(id=f'lugar_{clave[0]}_{clave[1]}',nombre=f'{zona(x,y)} · {entorno} {sum(p["entorno"]==entorno for p in sitios)+1}',
            entorno=entorno,zona=zona(x,y),posicion=[x,y,z],orientacion=0))
    nodos,enlaces=leer_vehiculos(carpeta)
    rutas=[];claves=list(nodos);rng.shuffle(claves)
    for inicio in claves:
        if len(rutas)>=90:break
        a=nodos[inicio]
        if a[2]<1 or max(abs(a[0]),abs(a[1]))>2800 or any(math.dist(a[:2],r['puntos'][0][:2])<120 for r in rutas):continue
        camino=[inicio];actual=inicio;prev=None;longitud=0
        for _ in range(18):
            posibles=[]
            for vecino in enlaces.get(actual,[]):
                if vecino not in nodos or vecino in camino:continue
                b=nodos[vecino];p=nodos[actual];d=math.dist(p,b)
                if not 6<d<90 or abs(p[2]-b[2])>4:continue
                if prev:
                    u=(p[0]-prev[0],p[1]-prev[1]);v=(b[0]-p[0],b[1]-p[1])
                    cos=(u[0]*v[0]+u[1]*v[1])/(math.hypot(*u)*math.hypot(*v))
                    if cos<.85:continue
                else:cos=1
                # Comparar cinco muestras con la interpolación de los nodos de carretera.
                if any(abs(alturas.obtener_z(p[0]+(b[0]-p[0])*t,p[1]+(b[1]-p[1])*t)-(p[2]+(b[2]-p[2])*t))>2.5 for t in (0,.25,.5,.75,1)):continue
                posibles.append((cos,vecino,d))
            if not posibles:break
            _,vecino,d=max(posibles)
            prev=nodos[actual];actual=vecino;camino.append(actual);longitud+=d
            if longitud>=180:break
        if longitud<65 or len(camino)<3:continue
        puntos=[]
        for i,k in enumerate(camino):
            x,y,z=nodos[k]
            if max(abs(x),abs(y))>2800:break
            b=nodos[camino[min(i+1,len(camino)-1)]];p=nodos[camino[max(i-1,0)]]
            dx,dy=b[0]-p[0],b[1]-p[1];d=math.hypot(dx,dy)
            # Carril derecho del sentido de circulación, evitando el centro de la vía.
            x+=dy/d*1.8;y-=dx/d*1.8
            terreno=alturas.obtener_z(x,y)
            if abs(terreno-z)>2.5:break
            puntos.append([round(x,3),round(y,3),round(terreno+.65,3)])
        else:
            rutas.append(dict(id=f'auto_{inicio[0]}_{inicio[1]}',nombre=f'{zona(*a[:2])} · recorrido {len(rutas)+1}',
                zona=zona(*a[:2]),entorno=detectar_entorno_gta(*puntos[0]),puntos=puntos,longitud=round(sum(math.dist(p,q) for p,q in zip(puntos,puntos[1:])),1),
                comprobada_en_gta=False))
    if len(sitios)<100:raise ValueError(f'Solo {len(sitios)} ubicaciones: no se reemplazará el catálogo.')
    return dict(version=1,origen='Nodos peatonales y viales del GTA instalado, contrastados con mapa de alturas. No acredita colisiones.',
        ubicaciones=sitios,rutas_vehiculos=rutas)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--paths',type=Path,required=True);args=p.parse_args()
    datos=preparar(args.paths)
    (ROOT/'assets/ubicaciones_escena.json').write_text(json.dumps(datos,ensure_ascii=False,indent=2),encoding='utf-8')
    print(len(datos['ubicaciones']),'ubicaciones;',len(datos['rutas_vehiculos']),'rutas de vehículo')
    print({e:sum(p['entorno']==e for p in datos['ubicaciones']) for e in ('ciudad','campo','desierto','playa')})
