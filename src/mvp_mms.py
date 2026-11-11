"""Exportador MMS con rutas, clips, secuencias y vehículos, basado en las referencias del usuario."""
from src.paths import RESOURCE_ROOT, salida
import configparser
import io
import json
import math
from datetime import datetime
from pathlib import Path
from uuid import uuid4

ROOT = RESOURCE_ROOT
REFERENCIA = ROOT / 'templates/caminar_referencia.mms'
REFERENCIA_SEGUIMIENTO = ROOT / 'templates/seguimiento_vehiculo_referencia.mms'
POS_INICIO = (2870.32, -1069.19, 9.875)
POS_DESTINO = (2870.16, -1093.67, 9.875)


def heading(inicio, destino):
    return math.degrees(math.atan2(-(destino[0]-inicio[0]), destino[1]-inicio[1])) % 360


def rutas_caminata(inicio,destino,cantidad):
    distancia=math.dist(inicio[:2],destino[:2])
    if distancia<2 or not 1<=cantidad<=4:
        raise ValueError('Ruta o reparto invalidos.')
    dx,dy=destino[0]-inicio[0],destino[1]-inicio[1]
    rutas=[(tuple(inicio),tuple(destino))]
    for indice in range(2,cantidad+1):
        lateral=(1 if indice%2==0 else -1)*math.ceil((indice-1)/2)*1.5
        ox,oy=-dy/distancia*lateral,dx/distancia*lateral
        puntos=[(p[0]+ox,p[1]+oy,p[2]) for p in (inicio,destino)]
        if any(abs(p[0])>3000 or abs(p[1])>3000 for p in puntos):
            raise ValueError('Una ruta de los acompañantes queda fuera del mapa.')
        rutas.append(tuple(puntos))
    return rutas


def camara_angulos(camara, objetivo):
    dx, dy, dz = (b-a for a, b in zip(camara, objetivo))
    return 180 - math.degrees(math.atan2(dy, dx)) % 360, math.degrees(math.atan2(dz, math.hypot(dx, dy)))


def generar_mms(*, actor_id, inicio, destino, duracion=10, hora=12, clima=0,
                titulo='Caminata', descripcion='', camara='fija', dialogos=None, accion='caminar', animacion_sugerida=None, segundo_actor_id=None, actores_ids=None, minuto=0, animar_actores=None, tipo_movimiento='caminar', adaptar_camara=False, banda_sonora=None,reproduccion='auto',vehiculo_id=None,ruta_vehiculo_id=None,velocidad_kmh=35,pasos=None,roles=None,perfil_recorrido=None,vehiculo_en_movimiento=False):
    if camara=='automatica':
        # Compilar todas las tareas primero. El montaje se aplica una sola vez,
        # también cuando una composición llama recursivamente a este generador.
        datos=dict(locals())
        datos['camara']='seguimiento_trasero'
        from src.montaje_camaras import aplicar_montaje
        return aplicar_montaje(generar_mms(**datos))
    if accion=='animacion_sobre_vehiculo':
        datos=dict(locals())
        from src.animacion_vehiculo import compilar as compilar_techo
        return compilar_techo(datos)
    if accion=='secuencia':
        datos=dict(locals())
        from src.compilar_secuencia import compilar
        return compilar(datos)
    if accion=='vehiculo_autonomo':
        datos=dict(locals());datos['accion']='conducir_vehiculo'
        from src.compilar_secuencia import convertir_autonomo
        return convertir_autonomo(generar_mms(**datos),camara)
    ruta_conduccion=None
    if accion=='conducir_vehiculo':
        from src.ubicaciones_escena import elegir_ruta_vehiculo
        from src.conduccion import grabacion
        ruta_conduccion=elegir_ruta_vehiculo(identificador=ruta_vehiculo_id)
        destino=tuple(ruta_conduccion['puntos'][0])
        datos_grabacion=grabacion(ruta_conduccion['puntos'],duracion,velocidad_kmh)
    if tipo_movimiento not in ('caminar','correr','nadar','escaleras'):
        raise ValueError('Tipo de movimiento no soportado.')
    if camara not in ('fija','seguimiento_trasero','seguimiento_lateral','costado','giro_frontal','vehiculo_pov'):
        raise ValueError('Tipo de camara no soportado.')
    if camara=='vehiculo_pov' and accion not in ('entrar_vehiculo','conducir_vehiculo'):
        raise ValueError('La cámara desde el asiento requiere una escena con vehículo.')
    if actores_ids is None:
        actores_ids=[actor_id]+([segundo_actor_id] if segundo_actor_id is not None else [])
    if not isinstance(actores_ids,list) or not 1<=len(actores_ids)<=4 or actores_ids[0]!=actor_id:
        raise ValueError('Selecciona entre uno y cuatro personajes.')
    if any(not isinstance(i,int) or not (ROOT/f'assets/actors/{i}.png').is_file() for i in actores_ids):
        raise ValueError('Todos los personajes deben estar disponibles en el carrusel.')
    if destino is None and accion=='animacion':
        destino=(inicio[0],inicio[1]+3,inicio[2])
    if not isinstance(actor_id, int) or not (ROOT / f'assets/actors/{actor_id}.png').is_file():
        raise ValueError('Elige un personaje disponible en el carrusel.')
    if isinstance(duracion, bool) or not isinstance(duracion, int) or not 1 <= duracion <= 60:
        raise ValueError('La duracion debe ser de 1 a 60 segundos.')
    if not isinstance(hora, int) or not 0 <= hora <= 24:
        raise ValueError('Hora fuera de rango.')
    if not isinstance(minuto,int) or not 0<=minuto<=59:
        raise ValueError('Minuto fuera de rango.')
    if not isinstance(clima, int) or not 0 <= clima <= 22:
        raise ValueError('El clima debe ser un ID de GTA entre 0 y 22.')
    if len(inicio) != 3 or len(destino) != 3 or not all(math.isfinite(v) for v in (*inicio, *destino)):
        raise ValueError('Coordenadas invalidas.')
    if any(abs(p[0]) > 3000 or abs(p[1]) > 3000 or not -100 <= p[2] <= 2000 for p in (inicio, destino)):
        raise ValueError('Coordenadas fuera del mapa de San Andreas.')
    distancia = math.dist(inicio[:2], destino[:2])
    if not 2 <= distancia <= 150:
        raise ValueError('Marca inicio y destino a una distancia de 2 a 150 metros, sobre la misma calle.')
    if accion=='caminar':
        from src.perfil_ruta import error_pendiente,validar_perfil,puente_coincidente
        error=error_pendiente(inicio,destino,tipo_movimiento,'puente' if puente_coincidente(inicio,destino) else None)
        if error:raise ValueError(error)
        if perfil_recorrido is not None:perfil_recorrido=validar_perfil(perfil_recorrido,inicio,destino,tipo_movimiento)
    config = configparser.ConfigParser(interpolation=None, strict=True)
    config.optionxform = str
    config.read(REFERENCIA, encoding='utf-8-sig')
    giro = heading(inicio, destino) - heading(POS_INICIO, POS_DESTINO)
    rad = math.radians(giro)

    def mover(x, y, z):
        dx, dy = x-POS_INICIO[0], y-POS_INICIO[1]
        return (inicio[0]+dx*math.cos(rad)-dy*math.sin(rad),
                inicio[1]+dx*math.sin(rad)+dy*math.cos(rad), inicio[2]+z-POS_INICIO[2])

    def poner_xyz(seccion, claves, xyz):
        for clave, valor in zip(claves, xyz):
            config[seccion][clave] = f'{valor:.6f}'

    # Trasladar/rotar los puntos existentes, conservando los campos opacos del mod.
    for seccion, grupos in {
        'MISSION': [('LAST_X','LAST_Y','LAST_Z')],
        'OBJ_0': [('PUT_X','PUT_Y','PUT_Z'),('PLA_CUM_X','PLA_CUM_Y','PLA_CUM_Z'),('PLA_CUM_PX','PLA_CUM_PY','PLA_CUM_PZ')],
        'OBJ_1': [('X','Y','Z')],
    }.items():
        for claves in grupos:
            poner_xyz(seccion, claves, mover(*(float(config[seccion][k]) for k in claves)))
    poner_xyz('ACTOR_1', ('X','Y','Z'), inicio)
    poner_xyz('ACTION_A_1', ('X','Y','Z'), destino)
    # El ejemplo guarda el waypoint un metro por encima del origen de la accion.
    poner_xyz('ACTION_A_1', ('POINT_X1','POINT_Y1','POINT_Z1'), (destino[0],destino[1],destino[2]+(0 if tipo_movimiento=='nadar' else 1)))
    for seccion, claves in {'MISSION':['LAST_A'], 'OBJ_0':['PUT_A'], 'OBJ_1':['A']}.items():
        for clave in claves:
            config[seccion][clave] = f'{(float(config[seccion][clave])+giro)%360:.6f}'
    orientacion = heading(inicio, destino)
    config['ACTOR_1']['A'] = f'{orientacion:.6f}'
    config['ACTION_A_1']['A'] = config['ACTION_A_1']['POINT_A1'] = f'{orientacion:.6f}'
    config['ACTION_A_1']['POINT_MODE1']='2' if tipo_movimiento=='correr' else '1'
    posicion_camara = tuple(float(config['OBJ_0'][k]) for k in ('PLA_CUM_X','PLA_CUM_Y','PLA_CUM_Z'))
    objetivo = tuple(float(config['OBJ_0'][k]) for k in ('PLA_CUM_PX','PLA_CUM_PY','PLA_CUM_PZ'))
    ax, ay = camara_angulos(posicion_camara, objetivo)
    config['OBJ_0']['PLA_CUM_inputX'] = f'{ax:.6f}'
    config['OBJ_0']['PLA_CUM_inputY'] = f'{ay:.6f}'
    if camara in ('seguimiento_trasero','seguimiento_lateral'):
        ejemplo = configparser.ConfigParser(interpolation=None)
        ejemplo.optionxform = str
        ejemplo.read(REFERENCIA_SEGUIMIENTO,encoding='utf-8-sig')
        # En modo 6, los offsets del ejemplo son locales al actor: no rotarlos.
        seccion = 'OBJ_1' if camara == 'seguimiento_trasero' else 'OBJ_2'
        campos = ejemplo[seccion]
        origen = tuple(float(ejemplo['ACTOR_1'][k]) for k in ('X','Y','Z'))
        delta = math.radians(orientacion-float(ejemplo['ACTOR_1']['A']))
        for clave,valor in campos.items():
            if clave.startswith('PLA_CUM') or clave in ('CUM_ACTOR','CUM_VEH'):
                config['OBJ_1'][clave] = valor
        for claves in [('PLA_CUM_X','PLA_CUM_Y','PLA_CUM_Z'),('PLA_CUM_PX','PLA_CUM_PY','PLA_CUM_PZ')]:
            x,y,z = (float(campos[k]) for k in claves)
            dx,dy=x-origen[0],y-origen[1]
            punto=(inicio[0]+dx*math.cos(delta)-dy*math.sin(delta),
                   inicio[1]+dx*math.sin(delta)+dy*math.cos(delta), inicio[2]+z-origen[2])
            poner_xyz('OBJ_1',claves,punto)
        config['OBJ_1']['CUM_ACTOR'] = '1'
    if camara in ('fija','seguimiento_trasero','costado'):
        # Los tres planos fotografiados del ejemplo 1.87: OBJ_2, OBJ_3 y OBJ_4.
        ejemplo=configparser.ConfigParser(interpolation=None)
        ejemplo.optionxform=str
        ejemplo.read(REFERENCIA.parent/'camaras_usuario.mms',encoding='utf-8-sig')
        campos=ejemplo[{'fija':'OBJ_3','seguimiento_trasero':'OBJ_2','costado':'OBJ_4'}[camara]]
        origen=tuple(float(ejemplo['ACTOR_1'][k]) for k in ('X','Y','Z'))
        delta=math.radians(float(ejemplo['ACTOR_1']['A'])-orientacion)
        for clave in list(config['OBJ_1']):
            if clave.startswith('PLA_CUM') or clave in ('CUM_ACTOR','CUM_VEH'):
                del config['OBJ_1'][clave]
        for clave,valor in campos.items():
            if clave.startswith('PLA_CUM') or clave=='CUM_ACTOR':
                config['OBJ_1'][clave]=valor
        for claves in [('PLA_CUM_X','PLA_CUM_Y','PLA_CUM_Z'),('PLA_CUM_PX','PLA_CUM_PY','PLA_CUM_PZ')]:
            x,y,z=(float(campos[k]) for k in claves)
            dx,dy=x-origen[0],y-origen[1]
            poner_xyz('OBJ_1',claves,(inicio[0]+dx*math.cos(delta)-dy*math.sin(delta),
                inicio[1]+dx*math.sin(delta)+dy*math.cos(delta),inicio[2]+z-origen[2]))
        cam=tuple(float(config['OBJ_1'][k]) for k in ('PLA_CUM_X','PLA_CUM_Y','PLA_CUM_Z'))
        obj=tuple(float(config['OBJ_1'][k]) for k in ('PLA_CUM_PX','PLA_CUM_PY','PLA_CUM_PZ'))
        ax,ay=camara_angulos(cam,obj)
        config['OBJ_1']['PLA_CUM_inputX']=str(ax)
        config['OBJ_1']['PLA_CUM_inputY']=str(ay)
    # Campos sin parejas XYZ visibles: orientar sus angulos con el mismo giro.
    for seccion, clave in [('MISSION','LAST_CX'),('OBJ_0','PUT_CX')]:
        config[seccion][clave] = f'{(float(config[seccion][clave])-giro+180)%360-180:.6f}'
    config['ACTOR_1']['Model'] = str(actor_id)
    config['OBJ_1']['DIAL_TIME'] = str(duracion*1000)
    for objetivo in ('OBJ_0','OBJ_1'):
        config[objetivo]['GAME_TIME'] = str(hora%24)
        config[objetivo]['GAME_MTIME'] = str(minuto)
        config[objetivo]['GAME_WEATHER'] = str(clima)
        config[objetivo]['TIME_FREEZE'] = '1'
        config[objetivo]['WEATHER_FREEZE'] = '1'
    config['MISSION']['SHOW_INTRO'] = '0'
    # Cadena no vacia sin glifos: evitar el texto por defecto al terminar la mision.
    config['MISSION']['MPASS'] = '~n~'
    config['MISSION']['MFAIL'] = '~n~'
    # Claves leidas por el main.scm de Mission Maker instalado.
    for objetivo in ('OBJ_0','OBJ_1'):
        for clave in ('HUD_OFF','RADAR_OFF','TIME_OFF','ARMOUR_OFF','HEALTH_OFF','MONEY_OFF','WEAPON_OFF','AMMO_OFF'):
            config[objetivo][clave] = '1'
    # Evitar que texto del usuario introduzca secciones o claves nuevas.
    limpiar = lambda s: ' '.join(str(s).splitlines()).replace('[','(').replace(']',')')[:240]
    config['MISSION']['NAME'] = limpiar(titulo)
    config['MISSION']['DESCRIPT'] = limpiar(descripcion)
    ahora = datetime.now()
    config['MISSION']['Date'] = ahora.strftime('%d.%m.%Y')
    config['MISSION']['DateENG'] = ahora.strftime('%m/%d/%Y')
    if dialogos:
        if not isinstance(dialogos,list) or len(dialogos)>6 or any(not isinstance(t,str) or len(t)>220 or not t.strip() for t in dialogos):
            raise ValueError('Usa hasta 6 líneas de diálogo, de 1 a 220 caracteres cada una.')
        textos=[limpiar(t) for t in dialogos]
        minimos=[max(1500,math.ceil(len(t)/18*1000)) for t in textos]
        total_ms=duracion*1000
        if sum(minimos)>total_ms:
            raise ValueError(f'Los diálogos necesitan al menos {math.ceil(sum(minimos)/1000)} segundos. Aumenta la duración o acórtalos.')
        resto=total_ms-sum(minimos)
        base=dict(config['OBJ_1'])
        for i,(texto,minimo) in enumerate(zip(textos,minimos),1):
            seccion=f'OBJ_{i}'
            if seccion not in config: config.add_section(seccion)
            config[seccion].update(base)
            config[seccion]['TEXT']=texto
            config[seccion]['DIAL_TIME']=str(minimo+resto//len(textos)+(1 if i<=resto%len(textos) else 0))
        config['MISSION']['SELECTED_OBJ']=str(len(textos))
    if accion not in ('caminar','animacion','entrar_vehiculo','conducir_vehiculo'):
        raise ValueError('Accion no soportada.')
    if accion in ('entrar_vehiculo','conducir_vehiculo'):
        from src.catalogos_entidades import disponibles
        if len(actores_ids)!=1 or vehiculo_id not in {o['model_id'] for o in disponibles('vehicles')}:
            raise ValueError('Selecciona un vehículo disponible y un único personaje para esta acción.')
        referencia=configparser.ConfigParser(interpolation=None);referencia.optionxform=str
        referencia.read(RESOURCE_ROOT/'templates/vehiculo_usuario.mms',encoding='utf-8-sig')
        config['Vehicle_1']=dict(referencia['Vehicle_1'])
        if ruta_conduccion:orientacion=heading(*ruta_conduccion['puntos'][:2])
        config['Vehicle_1'].update(OBJ='0',Model=str(vehiculo_id),X=str(destino[0]),Y=str(destino[1]),Z=str(destino[2]+(0 if ruta_conduccion else .5)),
            A=str(orientacion),AXX='0',AXY='0',AXZ=str(math.sin(math.radians(orientacion)/2)),AXA=str(math.cos(math.radians(orientacion)/2)),Doors='0')
        # Una sola tarea nativa se acerca y entra: sin ruta concurrente ni coche que arranque solo.
        config['ACTION_A_1']=dict(referencia['ACTION_A_1'])
        config['ACTION_A_1'].update(OBJ='0',SPHERE_ACTOR='1',SPHERE_VEH2='1',SPHERE_TYPE='2',
            X=str(destino[0]),Y=str(destino[1]),Z=str(destino[2]),A=str(orientacion))
    if accion=='caminar':
        # Rutas paralelas, con la misma tarea y orientación del ejemplo validado.
        rutas=rutas_caminata(inicio,destino,len(actores_ids))
        for indice,modelo in enumerate(actores_ids[1:],2):
            origen,fin=rutas[indice-1]
            config[f'ACTOR_{indice}']=dict(config['ACTOR_1'])
            config[f'ACTOR_{indice}'].update(Model=str(modelo),X=str(origen[0]),Y=str(origen[1]))
            config[f'ACTION_A_{indice}']=dict(config['ACTION_A_1'])
            tarea=config[f'ACTION_A_{indice}']
            tarea['SPHERE_ACTOR']=str(indice)
            for k,valor in [('X',fin[0]),('Y',fin[1]),('POINT_X1',fin[0]),('POINT_Y1',fin[1])]:
                tarea[k]=str(valor)
        if perfil_recorrido is not None:
            from src.perfil_ruta import campos_waypoints
            for indice,(origen,fin) in enumerate(rutas,1):
                ox,oy=origen[0]-inicio[0],origen[1]-inicio[1]
                puntos=[(p[0]+ox,p[1]+oy,p[2]) for p in perfil_recorrido[1:]]
                config[f'ACTION_A_{indice}'].update(campos_waypoints(puntos,tipo_movimiento,orientacion))
    if accion == 'animacion':
        from src.catalogo_animaciones import cargar_opciones_animaciones
        opcion=next((o for o in cargar_opciones_animaciones() if o['id']==animacion_sugerida),None)
        if opcion is None:
            raise ValueError('La animacion no pertenece al catalogo.')
        from src.reproduccion_animaciones import decidir_reproduccion
        modo,_=decidir_reproduccion(animacion_sugerida,descripcion,reproduccion)
        config.remove_section('ACTION_A_1')
        config['ACTION_A_1']={
            'Created':'1','Type':'3','OBJ':'0','X':str(inicio[0]),'Y':str(inicio[1]),'Z':str(inicio[2]),
            'A':str(orientacion),'SPHERE_TYPE':'0','SPHERE_ACTOR':'1',
            'Loop':'1' if modo=='bucle' else '0','Freeze':'1' if modo=='mantener' else '0','Move':'0','Indestruct':'1','Progress':'0','Speed':'1','TP':'0',
            'ANIM':opcion['anim'],'IFP':opcion['lib'],'LOG1':'MMS193','LOG2':'MMS304'}
        for indice,modelo in enumerate(actores_ids[1:],2):
            dx,dy=destino[0]-inicio[0],destino[1]-inicio[1]
            # Arco frente al actor principal, dejando espacio entre los participantes.
            lateral=(indice-2-(len(actores_ids)-2)/2)*1.8
            x=inicio[0]+2*dx/distancia-lateral*dy/distancia
            y=inicio[1]+2*dy/distancia+lateral*dx/distancia
            config[f'ACTOR_{indice}']=dict(config['ACTOR_1'])
            config[f'ACTOR_{indice}'].update(Model=str(modelo),X=str(x),Y=str(y),Z=str(inicio[2]),
                A=str(heading((x,y,inicio[2]),inicio)))
        participantes=[1] if animar_actores is None else animar_actores
        if not participantes or any(not isinstance(i,int) or not 1<=i<=len(actores_ids) for i in participantes):
            raise ValueError('Participantes de animacion fuera del reparto.')
        base=dict(config['ACTION_A_1'])
        config.remove_section('ACTION_A_1')
        for numero,participante in enumerate(dict.fromkeys(participantes),1):
            actor=config[f'ACTOR_{participante}']
            config[f'ACTION_A_{numero}']=dict(base,SPHERE_ACTOR=str(participante),
                X=actor['X'],Y=actor['Y'],Z=actor['Z'],A=actor['A'])
    if adaptar_camara:
        from src.encuadre_escena import adaptar_encuadre
        adaptar_encuadre(config,camara,inicio,destino,orientacion,len(actores_ids),accion=='animacion')
    if camara=='giro_frontal':
        from src.encuadre_escena import giro_frontal
        giro_frontal(config,inicio,orientacion,len(actores_ids),duracion)
    if ruta_conduccion:
        from src.conduccion import secuencia, identificador_grabacion
        carrec=identificador_grabacion(datos_grabacion)
        secuencia(config,ruta_conduccion,duracion,carrec,camara,datos_grabacion)
    elif accion=='entrar_vehiculo' and camara=='vehiculo_pov':
        from src.conduccion import camara_vehiculo
        for nombre in ('OBJ_0','OBJ_1'):camara_vehiculo(config[nombre],destino,'pov',orientacion)
    if banda_sonora:
        from src.banda_sonora import configuracion_musica
        config['OBJ_0'].update(configuracion_musica(banda_sonora))
    stream = io.StringIO()
    config.write(stream, space_around_delimiters=False)
    return stream.getvalue().replace('\n','\r\n')


def exportar_escena(*, plan=None, **datos):
    from src.escenas_semanticas import usa_recorrido_vehicular
    from src.preferencias_camara import preferencia_camara
    datos.setdefault('camara',preferencia_camara(datos.get('descripcion','')))
    if (usa_recorrido_vehicular(datos) or datos.get('accion')=='animacion_sobre_vehiculo') and not datos.get('ruta_vehiculo_id'):
        from src.ubicaciones_escena import elegir_ruta_vehiculo
        datos['ruta_vehiculo_id']=elegir_ruta_vehiculo()['id']
    contenido = generar_mms(**datos)
    carpeta = salida(ROOT) / 'salida_mms'
    carpeta.mkdir(parents=True,exist_ok=True)
    if datos.get('banda_sonora'):
        from src.banda_sonora import copiar_pista
        copiar_pista(datos['banda_sonora'],carpeta)
    if usa_recorrido_vehicular(datos):
        from src.ubicaciones_escena import elegir_ruta_vehiculo
        from src.conduccion import grabacion
        ruta_coche=elegir_ruta_vehiculo(identificador=datos['ruta_vehiculo_id'])
        cfg=configparser.ConfigParser(interpolation=None);cfg.optionxform=str;cfg.read_string(contenido)
        carrec=cfg['ACTION_V_1']['Carrec']
        archivo_carrec=carpeta/'Carrec'/f'CARREC{carrec}.rrr'
        archivo_carrec.parent.mkdir(exist_ok=True)
        datos_carrec=grabacion(ruta_coche['puntos'],datos.get('duracion',10),datos.get('velocidad_kmh',35))
        # No sobrescribir una grabación que otra misión ya utiliza, incluso ante colisión de ID.
        try:
            with archivo_carrec.open('xb') as f:f.write(datos_carrec)
        except FileExistsError:
            if archivo_carrec.read_bytes()!=datos_carrec:
                raise ValueError('Colisión de identificador CARREC: existe otra grabación. No se sobrescribió.')
    ruta = carpeta / (datetime.now().strftime('caminata_%Y%m%d_%H%M%S_') + uuid4().hex[:6] + '.mms')
    with ruta.open('xb') as f:
        f.write(contenido.encode('utf-8'))
    from src.paquete_mision import dependencias
    dependencias(ruta)  # No anunciar una exportación sin su grabación válida.
    ruta.with_suffix('.json').write_text(json.dumps(dict(elecciones=datos, plan=plan), ensure_ascii=False, indent=2), encoding='utf-8')
    return ruta
