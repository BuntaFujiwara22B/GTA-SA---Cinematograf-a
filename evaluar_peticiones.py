"""Genera y comprueba peticiones sin API ni crear miles de archivos .mms."""
import configparser
import json
from pathlib import Path
from collections import Counter
from src.catalogo_animaciones import cargar_opciones_animaciones
from src.mvp_plan import plan_local, validar_plan
from src.mvp_mms import generar_mms, POS_INICIO

ROOT=Path(__file__).resolve().parent
# Expectativas revisadas a partir de entradas reales, independientes de la búsqueda.
ACCIONES=[
    ('bailar','bailen','DANCE:3:DANCING:dance_loop'),
    ('saludar','saluden','STAND:90:ON_LOOKERS:wave_loop'),
    ('aplaudir','aplaudan','DANCE:1:DANCING:bd_clap'),
    ('rendirse','se rindan','STAND:1:ped:handsup'),
    ('mirar','miren a los lados','STAND:2:ped:roadcross'),
    ('rascarse','se rasquen','STAND:6:ped:XPRESSscratch'),
    ('tumbarse','se tumben','LAY:2:BEACH:Lay_Bac_Loop'),
    ('vomitar','vomiten','STAND:40:food:EAT_Vomit_P'),
    ('sorpresa','muestren sorpresa','MIMIC:3:ped:facsurp'),
    ('hablar','hablen','CHAT:5:ped:IDLE_chat'),
]


def generar_casos():
    casos=[]
    for familia,verbo,identificador in ACCIONES:
        for cantidad in range(1,5):
            for lugar in ('un puente','la playa','el campo','una plaza','el desierto'):
                for segundos in (5,10,15,20,30,60):
                    singular={'bailen':'baile','saluden':'salude','aplaudan':'aplauda','se rindan':'se rinda',
                        'miren a los lados':'mire a los lados','se rasquen':'se rasque','se tumben':'se tumbe',
                        'vomiten':'vomite','muestren sorpresa':'muestre sorpresa','hablen':'hable'}
                    sujeto='un personaje' if cantidad==1 else f'{cantidad} personajes'
                    texto=f"Quiero que {sujeto} {singular[verbo] if cantidad==1 else verbo} en {lugar} durante {segundos} segundos"
                    casos.append(dict(texto=texto,tipo='lenguaje_natural',familia=familia,
                        valido=True,animacion=identificador,actores=cantidad,duracion=segundos))
    for o in cargar_opciones_animaciones():
        casos.append(dict(texto=f"Reproduce el clip {o['id']} con 1 personaje durante 10 segundos",
            tipo='clip_explicito',familia=o['categoria'],valido=True,animacion=o['id'],actores=1,duracion=10))
    for cantidad in (5,6,7,10):
        for segundos in (5,10,30,60):
            casos.append(dict(texto=f'{cantidad} personajes bailan durante {segundos} segundos',tipo='limite_reparto',valido=False))
    for cantidad in range(1,5):
        for segundos in (0,61,90,120):
            casos.append(dict(texto=f'{cantidad} personajes bailan durante {segundos} segundos',tipo='limite_duracion',valido=False))
    for texto in ('un personaje conduce un carro y dispara','camina y dispara','un personaje baila y luego conduce',
        'cinco personajes caminan por una avenida','un personaje no baila','crea un dragon volando'):
        casos.append(dict(texto=texto,tipo='mecanica_no_implementada',valido=False))
    return casos


def evaluar(casos):
    fallos=[]
    for i,c in enumerate(casos):
        try:
            plan=validar_plan(plan_local(c['texto']),c['texto'])
            if plan.es_valido!=c['valido']:raise ValueError('aceptacion incorrecta')
            if not c['valido']:continue
            if (plan.animacion_sugerida,plan.cantidad_actores,plan.duracion_sugerida)!=(c['animacion'],c['actores'],c['duracion']):
                raise ValueError('plan diferente al esperado')
            contenido=generar_mms(actor_id=112,actores_ids=[112]*c['actores'],inicio=POS_INICIO,destino=None,
                accion=plan.accion,animacion_sugerida=plan.animacion_sugerida,
                animar_actores=plan.animar_actores,duracion=plan.duracion_sugerida)
            ini=configparser.ConfigParser(interpolation=None);ini.optionxform=str;ini.read_string(contenido)
            for n in plan.animar_actores:
                acciones=[ini[s] for s in ini.sections() if s.startswith('ACTION_A_') and ini[s].get('SPHERE_ACTOR')==str(n)]
                if len(acciones)!=1 or acciones[0]['Type']!='3':raise ValueError('falta accion de participante')
            if sum(int(ini[s]['DIAL_TIME']) for s in ini if s.startswith('OBJ_') and ini[s].get('Type')=='6')!=c['duracion']*1000:
                raise ValueError('duracion exportada incorrecta')
        except Exception as e:
            fallos.append(dict(caso=i,texto=c['texto'],error=str(e)))
    return dict(total=len(casos),correctos=len(casos)-len(fallos),fallos=fallos,
        distribucion=dict(Counter(c['tipo'] for c in casos)),
        alcance='Pruebas locales de interpretacion y estructura MMS. No evalua calidad visual ni respuestas reales de Gemini.')


if __name__=='__main__':
    carpeta=ROOT/'evaluaciones';carpeta.mkdir(exist_ok=True)
    casos=generar_casos()
    (carpeta/'peticiones_catalogo.json').write_text(json.dumps(casos,ensure_ascii=False,indent=2),encoding='utf-8')
    reporte=evaluar(casos)
    (carpeta/'resultado_peticiones.json').write_text(json.dumps(reporte,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(total=reporte['total'],correctos=reporte['correctos'],fallos=reporte['fallos'][:8]),ensure_ascii=False))
    raise SystemExit(bool(reporte['fallos']))
