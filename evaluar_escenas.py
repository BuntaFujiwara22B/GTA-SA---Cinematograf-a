"""Corpus natural y evaluación reproducible: plan, reparto, lugar y MMS.

No usa peticiones de clips por ID para inflar la cobertura. Por defecto no consume API.
--proveedor gemini permite medir respuestas reales, con pausa y resultados reanudables.
"""
import argparse
import configparser
import hashlib
import itertools
import json
import math
import time
from collections import Counter
from pathlib import Path
from src.mvp_plan import plan_local, validar_plan, analizar_peticion_final, estado_proveedores, PlanMVP
from src.propuesta_escena import completar_propuesta
from src.mvp_mms import generar_mms
from src.ubicaciones_escena import ubicaciones, elegir_ruta_vehiculo, puntos_entrada

ROOT=Path(__file__).resolve().parent
# Estas expectativas son contratos escritos a partir del mod, no respuestas del analizador.
GESTOS=[
    ('baila','bailan','DANCE:3:DANCING:dance_loop'),
    ('saluda','saludan','STAND:90:ON_LOOKERS:wave_loop'),
    ('aplaude','aplauden','DANCE:1:DANCING:bd_clap'),
    ('se rinde','se rinden','STAND:1:ped:handsup'),
    ('mira a los lados','miran a los lados','STAND:2:ped:roadcross'),
    ('se rasca','se rascan','STAND:6:ped:XPRESSscratch'),
    ('se tumba','se tumban','LAY:2:BEACH:Lay_Bac_Loop'),
    ('vomita','vomitan','STAND:40:food:EAT_Vomit_P'),
    ('muestra sorpresa','muestran sorpresa','MIMIC:3:ped:facsurp'),
    ('conversa','conversan','CHAT:5:ped:IDLE_chat'),
    ('se estira','se estiran','STAND:113:PLAYIDLES:stretch'),
    ('niega con la cabeza','niegan con la cabeza','STAND:163:urbanize:shakehead_1'),
    ('se muestra cansado','se muestran cansados','STAND:146:MMR:idle_tired'),
    ('se asusta','se asustan','STAND:70:ON_LOOKERS:panic_cower'),
    ('celebra','celebran','STAND:173:urbanize:cheers_1'),
    ('se muestra enfadado','se muestran enfadados','MIMIC:1:ped:facanger'),
    ('se muestra curioso','se muestran curiosos','MIMIC:6:ped:facurios'),
    ('fuma','fuman','STAND:133:SMOKING:M_smk_drag'),
    ('se ríe','se ríen','CHAT:52:RAPPING:Laugh_01'),
    ('bebe','beben','STAND:46:GANGS:drnkbr_prtl'),
    ('come','comen','STAND:37:food:EAT_Burger'),
    ('habla por teléfono','hablan por teléfono','STAND:44:ped:phone_talk'),
]
SUJETOS=[('persona','personas','civil'),('granjero','granjeros','granjero'),
    ('policía','policías','policia'),('bombero','bomberos','bombero'),
    ('paramédico','paramédicos','paramedico'),('soldado','soldados','militar')]
LUGARES=[('una calle de Los Santos','ciudad',None),('el campo','campo',None),
    ('la playa','playa','playa'),('el desierto','desierto',None),
    ('un puente','ciudad','puente'),('una calle de San Fierro','ciudad',None)]
AMBIENTES=[('',{}),(' bajo la lluvia',{'clima':8}),(' al atardecer',{'hora':18}),
    (' al amanecer',{'hora':6}),(' de noche',{'hora':22}),(' con niebla',{'clima':9})]
EQUIVALENTES={
    'DANCE:3:DANCING:dance_loop':{'DANCE:3:DANCING:dance_loop','DANCE:6:DANCING:DAN_Loop_A'},
    'DANCE:1:DANCING:bd_clap':{'DANCE:1:DANCING:bd_clap','DANCE:2:DANCING:bd_clap1'},
    'MIMIC:3:ped:facsurp':{'MIMIC:3:ped:facsurp','MIMIC:4:ped:facsurpm'},
}


def corpus():
    casos=[]
    def agregar(texto,acciones,cantidad=1,roles=None,entorno='ciudad',lugar=None,duracion=30,**extras):
        casos.append(dict(texto=texto,esperado=dict(valido=True,acciones=acciones,actores=cantidad,
            roles=roles or ['civil']*cantidad,entorno=entorno,lugar=lugar,duracion=duracion,**extras)))
    # Los cinco ejemplos del usuario, con sus contratos completos.
    agregar('una persona salta, baila y corre',['saltar',GESTOS[0][2],'correr'],duracion=10)
    agregar('un auto conduce solo en la cuidad',['vehiculo_autonomo'],visibles=0,duracion=10)
    agregar('dos personas se saludan en un puente',[GESTOS[1][2]],2,lugar='puente',duracion=10)
    agregar('3 granjeros caminan por el campo',['caminar'],3,['granjero']*3,'campo',duracion=10)
    agregar('un policia le apunta con un arma a un criminal',['apuntar'],2,['policia','criminal'],duracion=10)
    agregar('una persona salta, luego camina por una calle',['saltar','caminar'],duracion=10)
    # 408 escenas de gestos con reparto, roles, sitios y ambiente distintos.
    for g,(sing,plural,clip) in enumerate(GESTOS):
        for r,(nombre,nombres,rol) in enumerate(SUJETOS):
            for n in range(1,5):
                sitio,entorno,lugar=LUGARES[(g+r+n)%len(LUGARES)]
                ambiente,esperado=AMBIENTES[(g*3+r+n)%len(AMBIENTES)]
                if entorno=='campo' and 'clima' in esperado and esperado['clima']==8:esperado=dict(esperado,clima=16)
                sujeto=f'una {nombre}' if nombre=='persona' and n==1 else f'un {nombre}' if n==1 else f'{n} {nombres}'
                agregar(f'{sujeto} {sing if n==1 else plural} en {sitio}{ambiente} durante 30 segundos',
                    [clip],n,[rol]*n,entorno,lugar,**esperado)
    # 96 caminatas/carreras/saltos: las acciones tienen tareas nativas diferentes.
    for mov,sing,plu in [('caminar','camina','caminan'),('correr','corre','corren'),('saltar','salta','saltan'),('caminar','pasea','pasean')]:
        for nombre,nombres,rol in SUJETOS:
            for n in range(1,5):
                sitio,entorno,lugar=LUGARES[(n+len(casos))%len(LUGARES)]
                sujeto=f'un {nombre}' if n==1 else f'{n} {nombres}'
                agregar(f'{sujeto} {sing if n==1 else plu} por {sitio} durante 30 segundos',
                    [mov],n,[rol]*n,entorno,lugar)
    # 110 órdenes de acciones diferentes, no mil paráfrasis de bailar.
    verbos=[('salta','saltan','saltar'),('camina','caminan','caminar'),('corre','corren','correr'),*GESTOS[:8]]
    for k,(a,b) in enumerate(itertools.permutations(verbos,2)):
        for n in (1,2,4):
            nombre,nombres,rol=SUJETOS[(k+n)%len(SUJETOS)]
            sitio,entorno,lugar=LUGARES[(k+n)%len(LUGARES)]
            sujeto=f'un {nombre}' if n==1 else f'{n} {nombres}'
            agregar(f'{sujeto} {a[n>1]}, luego {b[n>1]} en {sitio} durante 30 segundos',
                [a[2],b[2]],n,[rol]*n,entorno,lugar)
    # Secuencias de tres tareas y orden no intercambiable.
    for k,terna in enumerate(itertools.islice(itertools.permutations(verbos,3),180)):
        n=(k%4)+1;nombre,nombres,rol=SUJETOS[k%len(SUJETOS)]
        sitio,entorno,lugar=LUGARES[k%len(LUGARES)]
        sujeto=f'un {nombre}' if n==1 else f'{n} {nombres}'
        agregar(f'{sujeto} {terna[0][n>1]}, después {terna[1][n>1]} y finalmente {terna[2][n>1]} en {sitio} durante 45 segundos',
            [v[2] for v in terna],n,[rol]*n,entorno,lugar,duracion=45)
    # Relaciones entre participantes: importa quién hace qué y a quién.
    for rol in ('criminal','granjero','civil','guardia'):
        nombre={'civil':'civil','guardia':'guardia','granjero':'granjero','criminal':'criminal'}[rol]
        for sitio,entorno,lugar in LUGARES:
            agregar(f'un policía apunta con un arma a un {nombre} en {sitio} durante 20 segundos',
                ['apuntar'],2,['policia',rol],entorno,lugar,duracion=20)
    for sujeto in ('una persona','un granjero','un policía','un paramédico'):
        rol={'una persona':'civil','un granjero':'granjero','un policía':'policia','un paramédico':'paramedico'}[sujeto]
        for coche in ('auto','taxi','coche','carro'):
            for ciudad in ('Los Santos','San Fierro','Las Venturas'):
                agregar(f'{sujeto} camina, se sube a un {coche} y maneja por {ciudad} durante 30 segundos',
                    ['conducir_vehiculo'],roles=[rol])
    for coche in ('auto','taxi','coche','carro'):
        for ciudad in ('Los Santos','San Fierro','Las Venturas'):
            agregar(f'un {coche} circula sin conductor por {ciudad} durante 30 segundos',['vehiculo_autonomo'],visibles=0)
    # Controles negativos: no confundir capacidad del mod con compilación disponible.
    for texto in ('cinco personas bailan','6 granjeros caminan','un personaje camina durante 90 segundos',
        'crea un dragón que vuele','un personaje dispara y luego conduce','un personaje no baila',
        'un personaje baila y luego conduce un coche','quiero algo indeterminado'):
        casos.append(dict(texto=texto,esperado=dict(valido=False),tipo='control_negativo'))
    # Composición con soporte móvil: no basta con aceptar la palabra fumar.
    agregar('una persona fuma en el techo de un auto de movimiento',['STAND:133:SMOKING:M_smk_drag'],
        duracion=10,techo=True,vehiculo_movimiento=True)
    from src.registro_capacidades import soportes_vehiculos
    for modelo in soportes_vehiculos():
        for sing,_,clip in [GESTOS[i] for i in (0,1,2,10,17,18)]:
            for mueve in (False,True):
                condicion='en movimiento' if mueve else 'estacionado'
                agregar(f'una persona {sing} en el techo de un {modelo["nombre"].lower()} {condicion} durante 20 segundos',
                    [clip],duracion=20,techo=True,vehiculo_movimiento=mueve,modelo_vehiculo=modelo['model_id'])
    assert len({c['texto'] for c in casos})==len(casos)
    for n,c in enumerate(casos,1):c['id']=f'escena_{n:04d}'
    return casos


def comprobar(caso,p):
    esperado=caso['esperado']
    if p.es_valido!=esperado['valido']:raise ValueError('Aceptación diferente del contrato esperado')
    if not p.es_valido:return
    for atributo,clave in [('cantidad_actores','actores'),('duracion_sugerida','duracion'),('entorno_sugerido','entorno'),
        ('clima_id_sugerido','clima'),('hora_sugerida','hora')]:
        if clave in esperado and getattr(p,atributo)!=esperado[clave]:raise ValueError(f'{clave}: {getattr(p,atributo)} != {esperado[clave]}')
    from src.reparto_escena import catalogo_personajes
    roles_por_id={a['model_id']:a['roles'] for a in catalogo_personajes()}
    for modelo,rol in zip(p.actores_ids_sugeridos,esperado['roles']):
        if rol!='civil' and rol not in roles_por_id[modelo]:raise ValueError('El personaje no tiene el rol pedido')
    inicio=(2100.,-1700.,13.);destino=(2100.,-1696.,13.)
    if p.ubicacion_id_sugerida:
        lugar=next(u for u in ubicaciones() if u['id']==p.ubicacion_id_sugerida)
        inicio=tuple(lugar['posicion']);destino=None
        if esperado.get('lugar')=='puente' and 'puente' not in lugar.get('etiquetas',[]):raise ValueError('La escena no está en un puente')
    if p.accion in ('conducir_vehiculo','vehiculo_autonomo'):
        inicio,destino=puntos_entrada(elegir_ruta_vehiculo(identificador=p.ruta_vehiculo_id))
    s=generar_mms(actor_id=p.actor_id_sugerido,actores_ids=p.actores_ids_sugeridos,inicio=inicio,destino=destino,
        duracion=p.duracion_sugerida,hora=p.hora_sugerida,clima=p.clima_id_sugerido,accion=p.accion,
        animacion_sugerida=p.animacion_sugerida,animar_actores=p.animar_actores,tipo_movimiento=p.tipo_movimiento,
        pasos=[a.model_dump() for a in p.pasos],vehiculo_id=p.vehiculo_id_sugerido,ruta_vehiculo_id=p.ruta_vehiculo_id,
        vehiculo_en_movimiento=p.vehiculo_en_movimiento,
        descripcion=caso['texto'])
    cfg=configparser.ConfigParser(interpolation=None);cfg.optionxform=str;cfg.read_string(s)
    visibles=sum(n.startswith('ACTOR_') for n in cfg.sections())
    if visibles!=esperado.get('visibles',esperado['actores']):raise ValueError('Cantidad de personajes visibles incorrecta')
    acciones=[]
    if esperado.get('techo'):
        anclaje=cfg['ACTION_A_1']
        if (p.accion,anclaje['Type'],anclaje['SPHERE_TYPE'])!=('animacion_sobre_vehiculo','2','6'):
            raise ValueError('Falta el anclaje real al vehículo')
        if ('ACTION_V_1' in cfg)!=esperado['vehiculo_movimiento']:raise ValueError('Se ha omitido o añadido movimiento del vehículo')
        if esperado.get('modelo_vehiculo') and int(cfg['Vehicle_1']['Model'])!=esperado['modelo_vehiculo']:raise ValueError('Modelo de coche distinto del pedido')
    for n in cfg.sections():
        if not n.startswith('ACTION_A_'):continue
        a=cfg[n]
        if a.get('Type')=='2' and a.get('SPHERE_TYPE')=='6':continue
        if a.get('Type')=='7':continue
        if a['Type']=='3':
            from src.capacidades_escena import opciones
            identificador=next(o['id'] for o in opciones() if o['anim']==a['ANIM'] and o['lib']==a['IFP'])
        elif a['Type']=='5' and a['SPHERE_TYPE']=='14':identificador='saltar'
        elif a['Type']=='1' and a['SPHERE_TYPE']=='2':
            identificador='apuntar'
            if a.get('SPHERE_ACTOR2')!='2' or int(cfg['ACTOR_1']['Weapon'])<22:raise ValueError('Falta arma o blanco real')
        elif a['Type']=='4':identificador='correr' if a['POINT_MODE1']=='2' else 'caminar'
        elif a['Type']=='2':identificador='conducir_vehiculo'
        else:raise ValueError('Tarea MMS no identificada')
        acciones.append((int(a['SPHERE_ACTOR']),int(a['OBJ']),identificador))
    participantes=[1] if esperado['acciones'] in (['apuntar'],['conducir_vehiculo']) else range(1,esperado['actores']+1)
    for participante in participantes:
        secuencia=[a for _,_,a in sorted((a for a in acciones if a[0]==participante),key=lambda a:a[1])]
        if p.accion=='vehiculo_autonomo':secuencia=['vehiculo_autonomo']
        if len(secuencia)!=len(esperado['acciones']) or any(a not in EQUIVALENTES.get(e,{e}) for a,e in zip(secuencia,esperado['acciones'])):
            raise ValueError(f'Actor {participante}: acciones exportadas {secuencia} != {esperado["acciones"]}')
    total=sum(int(cfg[s]['DIAL_TIME']) for s in cfg if s.startswith('OBJ_') and cfg[s].get('Type')=='6')
    from src.conduccion import PAUSA_ENTRADA_MS
    if total!=1000*esperado['duracion']+(PAUSA_ENTRADA_MS if p.accion=='conducir_vehiculo' else 0):raise ValueError('Duración MMS diferente de la esperada')
    for a in cfg:
        if a.startswith('ACTION_A_') and int(cfg[a]['OBJ'])>=len([s for s in cfg if s.startswith('OBJ_')])-1:
            raise ValueError('Acción programada después del final de la escena')
    return hashlib.sha256(s.encode()).hexdigest()


def ejecutar(casos,proveedor='local',limite=None,reintentar_fallos=False,texto=None):
    carpeta=ROOT/'evaluaciones';carpeta.mkdir(exist_ok=True)
    ruta=carpeta/f'resultado_escenas_{proveedor}.json'
    previos=json.loads(ruta.read_text(encoding='utf-8')).get('resultados',[]) if ruta.exists() and proveedor!='local' else []
    todos_previos=list(previos)
    anteriores_fallidos={c['texto']:c for c in previos if not c['correcto']} if reintentar_fallos else {}
    previos=[c for c in previos if c['correcto']] if reintentar_fallos else previos
    vistos={c['texto'] for c in previos};resultados=list(previos);hechos=0
    informe={}
    def guardar_informe():
        informe.update(total_corpus=len(casos),evaluados=len(resultados),correctos=sum(r['correcto'] for r in resultados),
            fallos=[r for r in resultados if not r['correcto']],proveedor=proveedor,
            alcance='Evalúa el sistema completo (análisis + validación + compilación), no la respuesta cruda del modelo ni la reproducción visual en GTA.',
            estado_proveedores=estado_proveedores(),
            contratos_acciones_distintos=len({tuple(c['esperado'].get('acciones',[])) for c in casos}),resultados=resultados)
        ruta.write_text(json.dumps(informe,ensure_ascii=False,indent=2),encoding='utf-8')
    for c in casos:
        if texto and c['texto']!=texto:continue
        if c['texto'] in vistos:continue
        if limite is not None and hechos>=limite:break
        antes=time.monotonic();p=None
        try:
            p=analizar_peticion_final(c['texto']) if proveedor!='local' else completar_propuesta(validar_plan(plan_local(c['texto']),c['texto']),c['texto'])
            if proveedor!='local' and not p.fuente.startswith(('Gemini',) if proveedor=='gemini' else ('Gemini','Groq')):
                print('Detenido: no hubo respuesta real del proveedor solicitado. El respaldo local no cuenta como evaluación de IA.',flush=True);break
            huella=comprobar(c,p)
            resultado=dict(id=c['id'],texto=c['texto'],correcto=True,huella_mms=huella)
        except Exception as e:resultado=dict(id=c['id'],texto=c['texto'],correcto=False,error=str(e))
        resultado.update(segundos=round(time.monotonic()-antes,3),fuente=p.fuente if p else None)
        if c['texto'] in anteriores_fallidos:resultado['intento_anterior']=anteriores_fallidos[c['texto']]
        if proveedor!='local' and p:resultado['plan']=p.model_dump()
        resultados.append(resultado);hechos+=1
        if hechos%100==0:print(f'{hechos} casos evaluados...',flush=True)
        if proveedor!='local':guardar_informe()
    textos_resultantes={r['texto'] for r in resultados}
    resultados.extend(r for r in todos_previos if r['texto'] not in textos_resultantes)
    guardar_informe()
    return resultados


def revalidar(casos,proveedor):
    """Comprueba respuestas ya registradas con el validador actual, sin consumir API."""
    ruta=ROOT/'evaluaciones'/f'resultado_escenas_{proveedor}.json'
    informe=json.loads(ruta.read_text(encoding='utf-8'))
    por_texto={c['texto']:c for c in casos}
    for r in informe['resultados']:
        if not r.get('plan'):continue
        anterior=dict(r);r['intento_antes_revalidar']=anterior
        try:
            p=completar_propuesta(validar_plan(PlanMVP.model_validate(r['plan']),r['texto']),r['texto'])
            r['huella_mms']=comprobar(por_texto[r['texto']],p)
            r['correcto']=True;r.pop('error',None);r['plan']=p.model_dump()
        except Exception as e:r['correcto']=False;r['error']=str(e)
        r['revalidacion_sin_consulta_api']=True
    informe.update(correctos=sum(r['correcto'] for r in informe['resultados']),
        fallos=[r for r in informe['resultados'] if not r['correcto']],
        nota_revalidacion='Se reutilizaron las respuestas reales guardadas para probar el validador actual; no se consultó de nuevo a los modelos.')
    ruta.write_text(json.dumps(informe,ensure_ascii=False,indent=2),encoding='utf-8')
    return informe['resultados']


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--proveedor',choices=['local','gemini','ia'],default='local')
    parser.add_argument('--limite',type=int);parser.add_argument('--reintentar-fallos',action='store_true')
    parser.add_argument('--revalidar',action='store_true');parser.add_argument('--texto');args=parser.parse_args()
    casos=corpus();carpeta=ROOT/'evaluaciones';carpeta.mkdir(exist_ok=True)
    (carpeta/'escenas_lenguaje_natural.json').write_text(json.dumps(casos,ensure_ascii=False,indent=2),encoding='utf-8')
    if args.texto and not any(c['texto']==args.texto for c in casos):parser.error('La frase no está en el corpus de evaluación.')
    resultados=revalidar(casos,args.proveedor) if args.revalidar else ejecutar(casos,args.proveedor,args.limite,args.reintentar_fallos,args.texto)
    print(json.dumps(dict(corpus=len(casos),evaluados=len(resultados),correctos=sum(r['correcto'] for r in resultados),
        primeros_fallos=[r for r in resultados if not r['correcto']][:12]),ensure_ascii=False))
