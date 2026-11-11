"""Prepara y valida una reparación; --aplicar conserva respaldo antes de modificar GTA."""
import argparse
import configparser
import json
import shutil
import io
import hashlib
from datetime import datetime
from pathlib import Path
from src.paquete_mision import dependencias,copiar_auxiliares

ROOT=Path(__file__).resolve().parent


def ajustar_camara_exterior(mision):
    from src.conduccion import camara_vehiculo
    mision=Path(mision)
    c=configparser.ConfigParser(interpolation=None);c.optionxform=str;c.read(mision,encoding='utf-8-sig')
    cambiadas=[]
    for s in c.sections():
        d=c[s]
        if not s.startswith('OBJ_') or d.get('PLA_CUM_MODE')!='7' or float(d.get('PLA_CUM_OZ','0'))<=6:continue
        vehiculo=c['Vehicle_'+d.get('CUM_VEH','1')]
        camara_vehiculo(d,tuple(float(vehiculo[k]) for k in ('X','Y','Z')),'trasera',float(vehiculo['A']))
        cambiadas.append(s)
    if cambiadas:
        backup=mision.with_suffix('.mms.antes_camara_exterior.bak')
        if not backup.exists():shutil.copy2(mision,backup)
        salida=io.StringIO();c.write(salida,space_around_delimiters=False)
        temporal=mision.with_suffix('.mms.tmp');temporal.write_bytes(salida.getvalue().replace('\n','\r\n').encode('utf-8'));temporal.replace(mision)
    return cambiadas


def preparar(mision,biblioteca,destino):
    mision,biblioteca,destino=Path(mision),Path(biblioteca),Path(destino)
    c=configparser.ConfigParser(interpolation=None);c.optionxform=str;c.read(mision,encoding='utf-8-sig')
    rutas=set()
    for s in c.values():
        if s.get('Carrec'):rutas.add(f"Carrec/CARREC{int(s['Carrec'])}.rrr")
        if s.get('GAME_MUSIC'):
            nombre=s['GAME_MUSIC']
            if Path(nombre).name!=nombre or '/' in nombre or '\\' in nombre:raise ValueError('Nombre de audio inválido.')
            rutas.add('Sounds/'+nombre)
    destino.mkdir(parents=True,exist_ok=True)
    salida=destino/mision.name
    shutil.copy2(mision,salida)
    for relativa in rutas:
        p=biblioteca/relativa
        if not p.is_file():raise ValueError('Falta en el proyecto: '+relativa)
        out=destino/relativa;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,out)
    # Comprueba que el Carrec empieza donde aparece el coche antes de copiar nada al juego.
    dependencias(salida)
    return salida


def ajustar_conduccion(mision,pausa_ms=1000):
    """Asocia MMS y grabación por contenido y acorta solo la espera posterior a la entrada."""
    from src.conduccion import identificador_grabacion
    if isinstance(pausa_ms,bool) or not isinstance(pausa_ms,int) or not 1<=pausa_ms<=5000:
        raise ValueError('La pausa después de entrar debe ser de 1 a 5000 milisegundos.')
    mision=Path(mision)
    archivos=dependencias(mision)
    cfg=configparser.ConfigParser(interpolation=None);cfg.optionxform=str
    cfg.read(mision,encoding='utf-8-sig')
    cambios=[]
    for nombre in cfg.sections():
        accion=cfg[nombre]
        if not nombre.startswith('ACTION_V_') or not accion.get('Carrec'):continue
        anterior=int(accion['Carrec'])
        datos=archivos[f'Carrec/CARREC{anterior}.rrr'].read_bytes()
        nuevo=identificador_grabacion(datos)
        grabacion=mision.parent/'Carrec'/f'CARREC{nuevo}.rrr'
        if grabacion.exists() and grabacion.read_bytes()!=datos:
            raise ValueError('Colisión CARREC en el paquete de reparación; se conserva la misión.')
        if not grabacion.exists():grabacion.write_bytes(datos)
        accion['Carrec']=str(nuevo)
        accion['CARREC_SHA256']=hashlib.sha256(datos).hexdigest()
        cambio=dict(accion=nombre,carrec_anterior=anterior,carrec_nuevo=nuevo,
                    sha256=accion['CARREC_SHA256'])
        objetivo=int(accion.get('OBJ','0'))
        pausa=f'OBJ_{objetivo}';entrada=f'OBJ_{objetivo-1}'
        if (objetivo>1 and pausa in cfg and entrada in cfg and
                cfg[entrada].get('Type')=='2' and cfg[entrada].get('SPHERE_TYPE')=='5' and
                cfg[pausa].get('Type')=='6'):
            cambio.update(pausa_anterior_ms=int(cfg[pausa]['DIAL_TIME']),pausa_nueva_ms=pausa_ms)
            cfg[pausa]['DIAL_TIME']=str(pausa_ms)
        cambios.append(cambio)
    if not cambios:raise ValueError('Esta misión no tiene una acción de conducción CARREC.')
    salida=io.StringIO();cfg.write(salida,space_around_delimiters=False)
    mision.write_bytes(salida.getvalue().replace('\n','\r\n').encode('utf-8'))
    dependencias(mision)
    return cambios


def aplicar_reparacion(paquete,mision):
    from src.paquete_mision import guardar_como
    paquete,mision=Path(paquete),Path(mision)
    dependencias(paquete)
    respaldo=mision.with_name(mision.name+'.antes_carrec_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.bak')
    shutil.copy2(mision,respaldo)
    guardar_como(paquete,mision,conservar_respaldo=False)
    return dict(respaldo=str(respaldo),archivos=list(dependencias(mision)))


def ajustar_musica(mision):
    """Comprueba la canción existente y conserva su huella completa en la misión."""
    mision=Path(mision);archivos=dependencias(mision)
    cfg=configparser.ConfigParser(interpolation=None);cfg.optionxform=str
    cfg.read(mision,encoding='utf-8-sig')
    cambios=[]
    for nombre in cfg.sections():
        seccion=cfg[nombre]
        if not seccion.get('GAME_MUSIC'):continue
        audio=archivos['Sounds/'+seccion['GAME_MUSIC']]
        seccion['MUSIC_SHA256']=hashlib.sha256(audio.read_bytes()).hexdigest()
        cambios.append(dict(objetivo=nombre,archivo=seccion['GAME_MUSIC'],
                            bytes=audio.stat().st_size,sha256=seccion['MUSIC_SHA256']))
    if not cambios:raise ValueError('La misión no tiene una canción seleccionada.')
    salida=io.StringIO();cfg.write(salida,space_around_delimiters=False)
    mision.write_bytes(salida.getvalue().replace('\n','\r\n').encode('utf-8'))
    dependencias(mision)
    return cambios


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mision',type=Path,required=True);p.add_argument('--aplicar',action='store_true');p.add_argument('--camara-exterior',action='store_true')
    p.add_argument('--conduccion',action='store_true',help='Repara la asociación CARREC y deja un segundo de pausa tras entrar.')
    p.add_argument('--musica',action='store_true',help='Entrega y verifica la canción que ya está seleccionada en el MMS.')
    args=p.parse_args()
    paquete=preparar(args.mision,ROOT/'salida_mms',ROOT/'.maintenance/reparacion_movimiento')
    reporte=dict(mision=str(args.mision),paquete_validado=str(paquete),archivos=list(dependencias(paquete)))
    if args.conduccion:reporte['conduccion']=ajustar_conduccion(paquete)
    if args.musica:reporte['musica']=ajustar_musica(paquete)
    if args.camara_exterior:
        reporte['camaras_ajustadas']=ajustar_camara_exterior(paquete)
    if args.aplicar:
        if args.conduccion or args.camara_exterior or args.musica:reporte['aplicacion']=aplicar_reparacion(paquete,args.mision)
        else:reporte['copiados']=copiar_auxiliares(paquete,args.mision.parent)
    reporte['archivos']=list(dependencias(paquete))
    print(json.dumps(reporte,ensure_ascii=False,indent=2))
