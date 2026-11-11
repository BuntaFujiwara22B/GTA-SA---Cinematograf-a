"""Agenda acciones MMS según OBJ: el paso N arranca al completar el objetivo anterior.

Campos contrastados con Mission Maker 1.87 EntityCreate.txt: Type=5/SPHERE_TYPE=14
salta; Type=1/SPHERE_TYPE=2 apunta; Type=7 interrumpe la tarea anterior.
"""
import configparser
import io
import math
from src.escenas_semanticas import PasoEscena, validar_pasos, duraciones_pasos


VELOCIDADES = {'caminar': 1.2, 'correr': 4.0, 'nadar': 1.0, 'escaleras': .7}


def capacidad_recorrido(pasos, duracion):
    pasos=[PasoEscena.model_validate(p) for p in pasos]
    return sum(VELOCIDADES.get(p.accion,0)*t*.8 for p,t in zip(pasos,duraciones_pasos(pasos,duracion)))


def compilar(datos):
    from src.mvp_mms import generar_mms, rutas_caminata, heading
    from src.capacidades_escena import opciones
    from src.reproduccion_animaciones import decidir_reproduccion
    pasos=[PasoEscena.model_validate(p) for p in datos.pop('pasos')]
    modelos=datos.get('actores_ids') or [datos['actor_id']]
    validar_pasos(pasos,len(modelos),datos.get('duracion',10))
    segundos=duraciones_pasos(pasos,datos.get('duracion',10))
    mueve=any(p.accion in VELOCIDADES for p in pasos)
    inicio=tuple(datos['inicio']);destino=datos.get('destino')
    if mueve:
        if destino is None:raise ValueError('Marca inicio y destino para la secuencia con movimiento.')
        if math.dist(inicio,destino)>capacidad_recorrido(pasos,datos.get('duracion',10))+.1:
            raise ValueError('El recorrido es demasiado largo para estas acciones. Acerca el destino o aumenta la duración.')
    perfil=(datos.get('perfil_recorrido') or [inicio,destino]) if mueve else None
    clip=next((p.animacion for p in pasos if p.animacion),opciones()[0]['id'])
    base=dict(datos,accion='caminar' if mueve else 'animacion',animacion_sugerida=clip,
        animar_actores=list(range(1,len(modelos)+1)),pasos=None)
    base.pop('roles',None)
    contenido=generar_mms(**base)
    cfg=configparser.ConfigParser(interpolation=None);cfg.optionxform=str;cfg.read_string(contenido)
    plantilla=dict(cfg['OBJ_1'])
    dialogos=[];acumulado=0
    for s in cfg:
        if s.startswith('OBJ_') and cfg[s].get('Type')=='6':
            fin=acumulado+int(cfg[s]['DIAL_TIME'])
            dialogos.append((acumulado,fin,cfg[s].get('TEXT')));acumulado=fin
    for s in list(cfg):
        if s.startswith('ACTION_A_') or (s.startswith('OBJ_') and s!='OBJ_0'):cfg.remove_section(s)
    tiempos=[0]
    for t in segundos:tiempos.append(tiempos[-1]+t*1000)
    cortes=sorted(set(tiempos+[f for _,f,_ in dialogos]))
    objetivo_por_tiempo={t:i for i,t in enumerate(cortes[:-1])}
    for i,(a,b) in enumerate(zip(cortes,cortes[1:]),1):
        cfg[f'OBJ_{i}']=dict(plantilla,DIAL_TIME=str(b-a))
        cfg[f'OBJ_{i}'].pop('TEXT',None)
        linea=next((txt for x,y,txt in dialogos if x<=a<y),None)
        if linea:cfg[f'OBJ_{i}']['TEXT']=linea
    cfg['MISSION']['SELECTED_OBJ']=str(len(cortes)-1)
    rutas=rutas_caminata(inicio,destino,len(modelos)) if mueve else None
    posiciones={n:tuple(float(cfg[f'ACTOR_{n}'][k]) for k in ('X','Y','Z')) for n in range(1,len(modelos)+1)}
    capacidades=[VELOCIDADES.get(p.accion,0)*s for p,s in zip(pasos,segundos)]
    avance={n:0.0 for n in posiciones}
    previas={n:None for n in posiciones}
    numero=0
    def agregar(campos):
        nonlocal numero
        numero+=1;cfg[f'ACTION_A_{numero}']={k:str(v) for k,v in campos.items()}
    for indice,paso in enumerate(pasos):
        obj=objetivo_por_tiempo[tiempos[indice]]
        for n in paso.actores:
            x,y,z=posiciones[n]
            actor=cfg[f'ACTOR_{n}']
            comunes=dict(Created=1,OBJ=obj,SPHERE_ACTOR=n,X=x,Y=y,Z=z,A=actor['A'])
            # Los handlers de ruta/clip/apuntar paran un ActorPoint previo y esperan
            # un frame (SCRIPTED_FIX). No borrar su bandera antes de esa espera:
            # el hilo antiguo podría observar la bandera de la ruta nueva.
            if previas[n] not in VELOCIDADES or paso.accion=='saltar':
                agregar(dict(comunes,Type=7,SPHERE_TYPE=0))
            if paso.accion in VELOCIDADES:
                total=sum(c for p,c in zip(pasos,capacidades) if n in p.actores)
                desde=avance[n]
                avance[n]+=capacidades[indice]/total
                a,b=rutas[n-1];f=min(1,avance[n])
                from src.perfil_ruta import recortar,campos_waypoints,validar_perfil
                ox,oy=a[0]-inicio[0],a[1]-inicio[1]
                tramo=[(p[0]+ox,p[1]+oy,p[2]) for p in recortar(perfil,desde,f)]
                validar_perfil(tramo,tramo[0],tramo[-1],paso.accion)
                fin=tramo[-1]
                agregar(dict(comunes,Type=4,SPHERE_TYPE=6,POINT_TOTAL=1,POINT_MODE1=2 if paso.accion=='correr' else 1,
                    POINT_X1=fin[0],POINT_Y1=fin[1],POINT_Z1=fin[2]+(0 if paso.accion=='nadar' else 1),
                    POINT_A1=heading(a,b),POINT_JUMP1=0,LOG1='MMS194',LOG2='MMS253'))
                cfg[f'ACTION_A_{numero}'].update(campos_waypoints(tramo[1:],paso.accion,heading(a,b)))
                posiciones[n]=fin
            elif paso.accion=='saltar':
                agregar(dict(comunes,Type=5,SPHERE_TYPE=14))
            elif paso.accion=='apuntar':
                actor['Weapon']='22'
                agregar(dict(comunes,Type=1,SPHERE_TYPE=2,SPHERE_ACTOR2=paso.objetivo_actor))
            else:
                opcion=next(o for o in opciones() if o['id']==paso.animacion)
                modo,_=decidir_reproduccion(paso.animacion,datos.get('descripcion',''),paso.reproduccion)
                agregar(dict(comunes,Type=3,SPHERE_TYPE=0,Loop=int(modo=='bucle'),Freeze=int(modo=='mantener'),
                    Move=0,Indestruct=1,Progress=0,Speed=1,TP=0,ANIM=opcion['anim'],IFP=opcion['lib'],LOG1='MMS193',LOG2='MMS304'))
            previas[n]=paso.accion
    salida=io.StringIO();cfg.write(salida,space_around_delimiters=False)
    return salida.getvalue().replace('\n','\r\n')


def convertir_autonomo(contenido,camara='fija'):
    """El parche nativo ACTION_V_EMPTY_DRIVER_PATCH añade el conductor invisible."""
    cfg=configparser.ConfigParser(interpolation=None);cfg.optionxform=str;cfg.read_string(contenido)
    planos=[dict(cfg[s]) for s in cfg if s.startswith('OBJ_') and cfg[s].get('Type')=='6' and s!='OBJ_2']
    for s in list(cfg):
        if s.startswith(('ACTOR_','ACTION_A_')) or (s.startswith('OBJ_') and s!='OBJ_0'):cfg.remove_section(s)
    cfg['ACTION_V_1']['OBJ']='0'
    cfg['MISSION']['SELECTED_ACT_A']='0';cfg['MISSION']['SPHERE_ACTOR']='0'
    coche=cfg['Vehicle_1']
    from src.conduccion import camara_vehiculo
    for i,plano in enumerate(planos,1):
        cfg[f'OBJ_{i}']=plano
        cfg[f'OBJ_{i}']['SPHERE_ACTOR']='0'
        camara_vehiculo(cfg[f'OBJ_{i}'],tuple(float(coche[k]) for k in ('X','Y','Z')),'pov' if camara=='vehiculo_pov' else 'trasera',float(coche['A']))
    camara_vehiculo(cfg['OBJ_0'],tuple(float(coche[k]) for k in ('X','Y','Z')),'pov' if camara=='vehiculo_pov' else 'trasera',float(coche['A']))
    cfg['MISSION']['SELECTED_OBJ']=str(len(planos))
    salida=io.StringIO();cfg.write(salida,space_around_delimiters=False)
    return salida.getvalue().replace('\n','\r\n')
