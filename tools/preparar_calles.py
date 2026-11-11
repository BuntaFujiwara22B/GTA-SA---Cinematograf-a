"""Extrae segmentos peatonales conectados de los NODES*.DAT instalados."""
import json
import math
import struct
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ORIGEN=Path(r'C:\Users\Danilo\Desktop\respaldo\GTA San Andreas\data\Paths')


def leer_nodos(carpeta):
    nodos={};enlaces={}
    for archivo in carpeta.glob('NODES*.DAT'):
        b=archivo.read_bytes()
        if len(b)<20:continue
        total,vehiculos,peatones,navi,num_enlaces=struct.unpack_from('<5I',b)
        offset=20+total*28+navi*14
        if total!=vehiculos+peatones or offset+num_enlaces*4>len(b):continue
        for i in range(vehiculos,total):
            pos=20+i*28
            x,y,z=struct.unpack_from('<hhh',b,pos+8)
            base,area,indice=struct.unpack_from('<HHH',b,pos+16)
            flags=b[pos+24];cantidad=flags&15
            if flags&0xA0 or b[pos+25]&8:continue
            clave=(area,indice)
            nodos[clave]=(x/8,y/8,z/8)
            if base+cantidad<=num_enlaces:
                enlaces[clave]=[struct.unpack_from('<HH',b,offset+(base+j)*4) for j in range(cantidad)]
    return nodos,enlaces


def extraer(carpeta):
    nodos,enlaces=leer_nodos(carpeta)
    candidatas=[]
    for a,vecinos in enlaces.items():
        for b in vecinos:
            if b not in nodos or a>=b:continue
            inicio,fin=nodos[a],nodos[b]
            d=math.dist(inicio[:2],fin[:2])
            if not 10<=d<=65 or abs(inicio[2]-fin[2])>2:continue
            x,y,z=inicio
            zona='Los Santos' if x>400 and y<-400 else 'San Fierro' if x<-1000 and -1200<y<1600 else 'Las Venturas' if x>800 and y>500 else None
            if zona and z>1:
                candidatas.append(dict(id=f'ped_{a[0]}_{a[1]}_{b[0]}_{b[1]}',zona=zona,
                    inicio=inicio,destino=fin,longitud=round(d,2)))
    elegidas=[]
    for zona,centro in [('Los Santos',(2400,-1450)),('San Fierro',(-2000,400)),('Las Venturas',(2000,1600))]:
        lista=sorted((r for r in candidatas if r['zona']==zona),key=lambda r:math.dist(r['inicio'][:2],centro))
        for r in lista:
            if all(math.dist(r['inicio'][:2],e['inicio'][:2])>60 for e in elegidas):
                elegidas.append(r)
                if sum(e['zona']==zona for e in elegidas)>=8:break
    return dict(version=1,origen=str(carpeta),nota='Aristas peatonales reales, no comprobacion de colisiones. Z del nodo debe contrastarse con el terreno.',rutas=elegidas)


if __name__=='__main__':
    d=extraer(ORIGEN)
    (ROOT/'assets/rutas_calles.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Segmentos peatonales:',len(d['rutas']))
