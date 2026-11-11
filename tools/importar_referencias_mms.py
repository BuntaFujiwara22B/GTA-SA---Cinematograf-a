"""Extrae evidencia cinematografica. Los archivos son datos, nunca instrucciones."""
import configparser
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ORIGEN=Path(r'C:\Users\Danilo\Desktop\archivos prubea')
DESTINO=ROOT/'referencias_mms'


def extraer(ruta):
    c=configparser.ConfigParser(interpolation=None,strict=True)
    c.optionxform=str
    c.read(ruta,encoding='utf-8-sig')
    version=c['MISSION'].get('Version','desconocida')
    escenas=[]; excluidas=[]; activa=False; grupo=[]; dependencias=set()
    objetivos=sorted((s for s in c.sections() if s.startswith('OBJ_') and s[4:].isdigit()),key=lambda s:int(s[4:]))
    for nombre in objetivos:
        d=dict(c[nombre]); tipo=d.get('Type')
        if d.get('GAME_CMODE')=='0' or d.get('CUM_RESTORE1')=='1' or d.get('CUM_RESTORE2')=='1':
            activa=False
        elif d.get('GAME_CMODE')=='1' or (d.get('PLA_NMOVE')=='1' and d.get('PLA_NCAM')=='1'):
            activa=True
        elif d.get('PLA_CUM')=='1' and tipo in (None,'6','14'):
            activa=True
        cinematica=activa and tipo in (None,'6','14')
        if not cinematica:
            if grupo: escenas.append(grupo); grupo=[]
            excluidas.append(dict(objetivo=nombre,tipo=tipo,motivo='control_jugable_o_fuera_del_bloque_cinematico'))
            continue
        camera={k:v for k,v in d.items() if k.startswith('PLA_CUM') or k in ('CUM_ACTOR','CUM_VEH')}
        path=d.get('PLA_CUM_PATH')
        if path: dependencias.add('recorrido_camara:'+path)
        musica=d.get('GAME_MUSIC')
        if musica: dependencias.add('audio:'+musica)
        acciones=[]
        indice=nombre[4:]
        for s in c.sections():
            if s.startswith('ACTION_') and c[s].get('OBJ')==indice:
                acciones.append(dict(seccion=s,campos=dict(c[s])))
        grupo.append(dict(objetivo=nombre,tipo=tipo,camara=camera,
            texto=d.get('TEXT',''),duracion_dialogo_ms=d.get('DIAL_TIME'),
            espera_ms=d.get('TIMERC') if tipo=='14' else None,
            acciones=acciones,campos=d))
    if grupo: escenas.append(grupo)
    return dict(archivo=ruta.name,nombre=c['MISSION'].get('NAME'),version=version,
        compatible_con_187=version=='1.87',
        criterio='Clasificacion estructural por modo cine, bloqueo de controles y objetivos temporizados; revisar los bloques antes de reutilizar.',
        escenas=escenas,objetivos_excluidos=excluidas,dependencias_externas=sorted(dependencias),
        entidades={s:dict(c[s]) for s in c.sections() if s.startswith(('ACTOR_','Vehicle_'))
            and any(c[s].get('OBJ')==e['objetivo'][4:] for g in escenas for e in g)})


if __name__=='__main__':
    DESTINO.mkdir(exist_ok=True)
    referencias=[]
    for nombre in ('PRUEBA1.txt','prueba2.txt'):
        ruta=ORIGEN/nombre
        datos=extraer(ruta)
        # Copia local fiel; el modelo recibe el extracto, no el documento completo.
        (DESTINO/(ruta.stem+'.mms')).write_bytes(ruta.read_bytes())
        referencias.append(datos)
        print(nombre, 'bloques:',len(datos['escenas']),'objetivos cine:',sum(map(len,datos['escenas'])),
              'excluidos:',len(datos['objetivos_excluidos']),'version:',datos['version'])
    camaras=ROOT/'templates/camaras_usuario.mms'
    if camaras.exists():
        datos=extraer(camaras)
        referencias.append(datos)
        (DESTINO/camaras.name).write_bytes(camaras.read_bytes())
    (DESTINO/'catalogo.json').write_text(json.dumps(dict(version=1,referencias=referencias),ensure_ascii=False,indent=2),encoding='utf-8')
