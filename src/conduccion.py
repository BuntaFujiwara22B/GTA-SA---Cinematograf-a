"""Secuencia nativa de entrada y recorrido CARREC; sin conductor invisible concurrente."""
import math
import struct
import hashlib
from src.paths import RESOURCE_ROOT
import configparser

FRAME=struct.Struct('<I3h6b4B3f')  # CVehicleStateEachFrame, 32 bytes
PAUSA_ENTRADA_MS = 1000


def identificador_grabacion(datos):
    """El ID identifica el contenido completo, no solo el nombre de una ruta mutable."""
    return 10000 + int(hashlib.sha256(datos).hexdigest()[:12], 16) % 900000


def grabacion(puntos,segundos,velocidad_kmh):
    if isinstance(velocidad_kmh,bool) or not isinstance(velocidad_kmh,(int,float)) or not math.isfinite(velocidad_kmh) or not 10<=velocidad_kmh<=90:
        raise ValueError('La velocidad debe estar entre 10 y 90 km/h.')
    if isinstance(segundos,bool) or not isinstance(segundos,int) or len(puntos)<2 or not 1<=segundos<=60:
        raise ValueError('Recorrido de conducción inválido.')
    longitudes=[math.dist(a,b) for a,b in zip(puntos,puntos[1:])]
    if min(longitudes)<.1:raise ValueError('La ruta tiene puntos repetidos.')
    total=sum(longitudes);vmax=velocidad_kmh/3.6
    tiempo=min(float(segundos),total/vmax+2)
    rampa=min(1.5,tiempo/4)
    recorrido=min(total,vmax*(tiempo-rampa))
    escala=recorrido/(tiempo-rampa)
    resultado=bytearray()
    for ms in range(0,segundos*1000+1,100):
        t=min(ms/1000,tiempo)
        if t<rampa:distancia=escala*t*t/(2*rampa);v=escala*t/rampa
        elif t>tiempo-rampa:
            pendiente=tiempo-t;distancia=recorrido-escala*pendiente*pendiente/(2*rampa);v=escala*pendiente/rampa
        else:distancia=escala*(t-rampa/2);v=escala
        tramo=0;resto=distancia
        while tramo<len(longitudes)-1 and resto>longitudes[tramo]:resto-=longitudes[tramo];tramo+=1
        a,b=puntos[tramo:tramo+2];f=min(1,resto/longitudes[tramo])
        pos=[a[i]+(b[i]-a[i])*f for i in range(3)]
        frente=[(b[i]-a[i])/longitudes[tramo] for i in range(3)]
        # Interpolar orientación cerca de los nodos para suavizar curvas moderadas.
        vecino=tramo+1 if f>.75 and tramo+1<len(longitudes) else tramo-1 if f<.25 and tramo>0 else tramo
        if vecino!=tramo:
            c,d=puntos[vecino:vecino+2]
            otro=[(d[i]-c[i])/longitudes[vecino] for i in range(3)]
            mezcla=(f-.75)*2 if f>.75 else (.25-f)*2
            frente=[x*(1-mezcla)+y*mezcla for x,y in zip(frente,otro)]
            norma=math.sqrt(sum(x*x for x in frente));frente=[x/norma for x in frente]
        h=math.hypot(frente[0],frente[1]);derecha=(frente[1]/h,-frente[0]/h,0)
        # Velocidad interna de SA: unidades por paso nominal de 1/50 segundo.
        velocidad=[max(-32767,min(32767,round(x*v/50*16383.5))) for x in frente]
        ejes=[max(-127,min(127,round(x*127))) for x in (*derecha,*frente)]
        resultado.extend(FRAME.pack(ms,*velocidad,*ejes,0,70 if v>.1 else 0,100 if t>=tiempo else 0,0,*pos))
    return bytes(resultado)


def camara_vehiculo(seccion,posicion,tipo='trasera',orientacion=0):
    for k in list(seccion):
        if k.startswith('PLA_CUM') or k in ('CUM_ACTOR','CUM_VEH'):del seccion[k]
    if tipo!='trasera':
        referencia=configparser.ConfigParser(interpolation=None);referencia.optionxform=str
        referencia.read(RESOURCE_ROOT/'templates/vehiculo_usuario.mms',encoding='utf-8-sig')
        origen=referencia['Vehicle_1']
        plano=referencia[{'frontal':'OBJ_1','pov':'OBJ_2','elevada':'OBJ_3'}[tipo]]
        seccion.update({k:v for k,v in plano.items() if k.startswith('PLA_CUM') or k in ('CUM_ACTOR','CUM_VEH','GAME_CMODE')})
        rad=math.radians(orientacion-float(origen['A']))
        for claves in (('PLA_CUM_X','PLA_CUM_Y','PLA_CUM_Z'),('PLA_CUM_PX','PLA_CUM_PY','PLA_CUM_PZ')):
            dx=float(plano[claves[0]])-float(origen['X']);dy=float(plano[claves[1]])-float(origen['Y'])
            punto=(posicion[0]+dx*math.cos(rad)-dy*math.sin(rad),
                posicion[1]+dx*math.sin(rad)+dy*math.cos(rad),posicion[2]+float(plano[claves[2]])-float(origen['Z']))
            seccion.update({k:str(v) for k,v in zip(claves,punto)})
        seccion['CUM_VEH']='1';seccion['CUM_ACTOR']='1'
        return
    x,y,z=posicion
    rad=math.radians(orientacion)
    cx,cy=x+5.92*math.sin(rad),y-5.92*math.cos(rad)
    seccion.update(PLA_CUM='1',PLA_CUM_MODE='7',CUM_VEH='1',CUM_ACTOR='1',PLA_CUM_ZOOM='70',
        PLA_CUM_OX='0',PLA_CUM_OY='-5.92',PLA_CUM_OZ='2.04',PLA_CUM_ORX='0',PLA_CUM_ORY='0',PLA_CUM_ORZ='0',
        PLA_CUM_X=str(cx),PLA_CUM_Y=str(cy),PLA_CUM_Z=str(z+2.04),
        PLA_CUM_PX=str(x),PLA_CUM_PY=str(y),PLA_CUM_PZ=str(z+1))


def secuencia(config,ruta,duracion,carrec,tipo_camara='fija',datos_grabacion=None):
    coche=config['Vehicle_1'];punto=ruta['puntos'][0]
    config['MISSION'].update(SELECTED_ACT_V='1')
    # OBJ_1 no se completa por un temporizador: espera a que ACTOR_1 esté en el coche.
    espera=dict(config['OBJ_1'])
    espera.update(Type='2',SPHERE_TYPE='5',SPHERE_ACTOR='1',MARKER_SIZE='0',MARKER_ARROW='0')
    for k in ('DIAL_TIME','TEXT'):espera.pop(k,None)
    planos=[dict(config[s]) for s in config if s.startswith('OBJ_') and config[s].get('Type')=='6']
    for s in list(config):
        if s.startswith('OBJ_') and s!='OBJ_0':config.remove_section(s)
    config['OBJ_1']=espera
    orientacion=float(coche['A'])
    camara_vehiculo(config['OBJ_1'],punto,'frontal',orientacion)
    config['OBJ_2']=dict(planos[0],DIAL_TIME=str(PAUSA_ENTRADA_MS))
    config['OBJ_2'].pop('TEXT',None)
    # En conducción: vista interior elegida o exterior cercana, sin toma cenital.
    tipo='pov' if tipo_camara=='vehiculo_pov' else 'trasera'
    camara_vehiculo(config['OBJ_2'],punto,tipo,orientacion)
    for numero,plano in enumerate(planos,3):
        # Conducción: conservar el plano elegido durante los diálogos.
        for k in list(plano):
            if k.startswith('PLA_CUM') or k in ('CUM_ACTOR','CUM_VEH'):del plano[k]
        config[f'OBJ_{numero}']=plano
    config['MISSION']['SELECTED_OBJ']=str(2+len(planos))
    config['ACTION_V_1']=dict(Created='1',Type='2',OBJ='2',Carrec=str(carrec),SPHERE_VEH='1',SPHERE_TYPE='0',
        X=coche['X'],Y=coche['Y'],Z=coche['Z'],A=coche['A'],
        CARR_X=coche['X'],CARR_Y=coche['Y'],CARR_Z=coche['Z'],CARR_A=coche['A'],
        AXX=coche['AXX'],AXY=coche['AXY'],AXZ=coche['AXZ'],AXA=coche['AXA'],LOG1='MMS325',LOG2='MMS325')
    if datos_grabacion:
        config['ACTION_V_1']['CARREC_SHA256'] = hashlib.sha256(datos_grabacion).hexdigest()
        # El ejemplo guarda en CARR_* el final de la grabación, no la posición de aparición.
        ultimo=FRAME.unpack_from(datos_grabacion,len(datos_grabacion)-FRAME.size)
        fin=ultimo[-3:];angulo=math.degrees(math.atan2(-ultimo[7],ultimo[8]))%360
        accion=config['ACTION_V_1']
        for claves in (('X','Y','Z'),('CARR_X','CARR_Y','CARR_Z')):
            accion.update({k:str(v) for k,v in zip(claves,fin)})
        accion.update(A=str(angulo),CARR_A=str(angulo),AXX='0',AXY='0',
            AXZ=str(math.sin(math.radians(angulo)/2)),AXA=str(math.cos(math.radians(angulo)/2)))
