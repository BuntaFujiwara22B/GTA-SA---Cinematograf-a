"""Composición nativa: anclar actor, reproducir clip sin TP y mover el vehículo.

EntityCreate.txt 1.87 carga ACTION_A antes de ACTION_V. El handler de animación
conserva el modo turret si SPHERE_TYPE=0 y TP=0. La posición necesita prueba en GTA.
"""
import configparser
import io
import math
from src.registro_capacidades import soportes_vehiculos
from src.escenas_semanticas import PasoEscena,validar_pasos,duraciones_pasos


def compilar(datos):
    from src.mvp_mms import generar_mms
    from src.ubicaciones_escena import elegir_ruta_vehiculo,puntos_entrada
    from src.capacidades_escena import opciones
    from src.reproduccion_animaciones import decidir_reproduccion
    from src.conduccion import camara_vehiculo
    modelos=datos.get('actores_ids') or [datos['actor_id']]
    if len(modelos)!=1:raise ValueError('El techo admite por ahora un personaje.')
    soporte=next((v for v in soportes_vehiculos() if v['model_id']==datos.get('vehiculo_id')),None)
    if soporte is None:raise ValueError('Ese vehículo no tiene una posición de techo preparada.')
    pasos=[PasoEscena.model_validate(p) for p in datos.get('pasos') or [dict(accion='animacion',animacion=datos.get('animacion_sugerida'))]]
    validar_pasos(pasos,1,datos.get('duracion',10))
    if any(p.accion!='animacion' for p in pasos):raise ValueError('Esta composición solo admite clips sin soltar el anclaje.')
    ruta=elegir_ruta_vehiculo(identificador=datos.get('ruta_vehiculo_id'))
    entrada,origen=puntos_entrada(ruta)
    base=dict(datos,accion='vehiculo_autonomo',inicio=entrada,destino=origen,ruta_vehiculo_id=ruta['id'],pasos=None,perfil_recorrido=None)
    base.pop('vehiculo_en_movimiento',None)
    texto=generar_mms(**base)
    cfg=configparser.ConfigParser(interpolation=None);cfg.optionxform=str;cfg.read_string(texto)
    # Las coordenadas iniciales coinciden con el offset local sobre el vehículo.
    angulo=float(cfg['Vehicle_1']['A']);rad=math.radians(angulo)
    ox,oy,oz=soporte['offset']
    posicion=(origen[0]+ox*math.cos(rad)-oy*math.sin(rad),origen[1]+ox*math.sin(rad)+oy*math.cos(rad),origen[2]+oz)
    actor_base=dict(datos,accion='animacion',inicio=posicion,destino=None,camara='fija',
        animacion_sugerida=pasos[0].animacion,pasos=None,perfil_recorrido=None,dialogos=None)
    actor_base.pop('vehiculo_en_movimiento',None)
    plantilla=configparser.ConfigParser(interpolation=None);plantilla.optionxform=str
    plantilla.read_string(generar_mms(**actor_base))
    cfg['ACTOR_1']=dict(plantilla['ACTOR_1'],OBJ='0',A=str(angulo),Weapon='0')
    cfg['MISSION'].update(SELECTED_ACT_A='1',SPHERE_ACTOR='1')
    comunes=dict(Created='1',SPHERE_ACTOR='1',X=str(posicion[0]),Y=str(posicion[1]),Z=str(posicion[2]),A=str(angulo))
    cfg['ACTION_A_1']=dict(comunes,OBJ='0',Type='2',SPHERE_TYPE='6',SPHERE_VEH2='1',CARRIAGE='0',
        T_X=str(ox),T_Y=str(oy),T_Z=str(oz),T_A=str(angulo),LOG1='MMS192',LOG2='MMS209')
    # La cámara conserva al personaje entero sobre el techo, sin plano cenital.
    camara_vehiculo(cfg['OBJ_0'],origen,'trasera',angulo)
    cfg['OBJ_0'].update(PLA_CUM_OY='-7.2',PLA_CUM_OZ=str(oz+1.5),PLA_CUM_Z=str(origen[2]+oz+1.5))
    planos=[];t=0
    for s in cfg:
        if s.startswith('OBJ_') and cfg[s].get('Type')=='6':
            fin=t+int(cfg[s]['DIAL_TIME']);planos.append((t,fin,dict(cfg[s])));t=fin
    tiempos=[0]
    for segundos in duraciones_pasos(pasos,datos.get('duracion',10)):tiempos.append(tiempos[-1]+segundos*1000)
    cortes=sorted(set(tiempos+[b for _,b,_ in planos]));indices={t:i for i,t in enumerate(cortes[:-1])}
    for s in list(cfg):
        if s.startswith('OBJ_') and s!='OBJ_0':cfg.remove_section(s)
    for i,(a,b) in enumerate(zip(cortes,cortes[1:]),1):
        plano=dict(next(p for ini,fin,p in planos if ini<=a<fin),DIAL_TIME=str(b-a),SPHERE_ACTOR='1')
        for k in list(plano):
            if k.startswith('PLA_CUM') or k in ('CUM_ACTOR','CUM_VEH'):del plano[k]
        cfg[f'OBJ_{i}']=plano
    for numero,p in enumerate(pasos,2):
        clip=next(o for o in opciones() if o['id']==p.animacion)
        modo,_=decidir_reproduccion(p.animacion,datos.get('descripcion',''),p.reproduccion)
        cfg[f'ACTION_A_{numero}']=dict(comunes,OBJ=str(indices[tiempos[numero-2]]),Type='3',
            SPHERE_TYPE='0',TP='0',Loop=str(int(modo=='bucle')),Freeze=str(int(modo=='mantener')),
            Move='0',Indestruct='1',Progress='0',Speed='1',ANIM=clip['anim'],IFP=clip['lib'],LOG1='MMS193',LOG2='MMS304')
    if not datos.get('vehiculo_en_movimiento',False):cfg.remove_section('ACTION_V_1')
    cfg['MISSION']['SELECTED_OBJ']=str(len(cortes)-1)
    cfg['MISSION']['SELECTED_ACT_A']=str(1+len(pasos))
    salida=io.StringIO();cfg.write(salida,space_around_delimiters=False)
    return salida.getvalue().replace('\n','\r\n')
