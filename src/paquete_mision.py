"""Entrega el MMS junto con sus dependencias, sin perder Sounds ni Carrec."""
import configparser
import io
import shutil
import zipfile
import math
import struct
import hashlib
import os
import tempfile
from datetime import datetime
from pathlib import Path


def dependencias(ruta):
    ruta=Path(ruta)
    ini=configparser.ConfigParser(interpolation=None);ini.optionxform=str
    ini.read(ruta,encoding='utf-8-sig')
    archivos={ruta.name:ruta}
    for s in ini.values():
        if s.get('GAME_MUSIC'):
            nombre=s['GAME_MUSIC']
            if Path(nombre).name!=nombre or '/' in nombre or '\\' in nombre:raise ValueError('Nombre de audio inválido.')
            archivos['Sounds/'+nombre]=ruta.parent/'Sounds'/nombre
        if s.get('Carrec'):
            numero=int(s['Carrec'])
            if not 1<=numero<=2147483647:raise ValueError('Identificador CARREC fuera de rango.')
            grabacion=ruta.parent/'Carrec'/f'CARREC{numero}.rrr'
            sin_extension=grabacion.with_suffix('')
            # SAMM quita .rrr al iniciar y lo restaura al cargar la misión.
            if grabacion.is_file() and sin_extension.is_file() and grabacion.read_bytes()!=sin_extension.read_bytes():
                raise ValueError(f'Hay dos grabaciones CARREC{numero} diferentes en la misma misión.')
            archivos[f'Carrec/CARREC{numero}.rrr']=grabacion if grabacion.is_file() else sin_extension
    for nombre,p in archivos.items():
        if not p.is_file():raise ValueError(f'Falta un archivo de la misión: {nombre}. Vuelve a generarla.')
    for s in ini.values():
        if s.get('GAME_MUSIC'):
            audio=archivos['Sounds/'+s['GAME_MUSIC']]
            if audio.stat().st_size==0:raise ValueError('El archivo de música está vacío.')
            if s.get('MUSIC_SHA256') and hashlib.sha256(audio.read_bytes()).hexdigest()!=s['MUSIC_SHA256']:
                raise ValueError('La canción no corresponde al contenido indicado por el MMS.')
        if s.get('Carrec'):
            datos=archivos[f"Carrec/CARREC{int(s['Carrec'])}.rrr"].read_bytes()
            seccion_vehiculo='Vehicle_'+s.get('SPHERE_VEH','1')
            if seccion_vehiculo not in ini:raise ValueError('El recorrido no tiene un vehículo asociado.')
            vehiculo=ini[seccion_vehiculo]
            if s.get('CARREC_SHA256') and hashlib.sha256(datos).hexdigest()!=s['CARREC_SHA256']:
                raise ValueError('La grabación CARREC no corresponde al contenido firmado por el MMS.')
            fin=tuple(float(s[k]) for k in ('CARR_X','CARR_Y','CARR_Z')) if all(k in s for k in ('CARR_X','CARR_Y','CARR_Z')) else None
            validar_grabacion(datos,tuple(float(vehiculo[k]) for k in ('X','Y','Z')),fin)
    return archivos


def validar_grabacion(datos,inicio,fin=None):
    """Un archivo con otro recorrido no es una dependencia válida aunque se llame igual."""
    if len(datos)<64 or len(datos)%32:raise ValueError('El archivo Carrec está incompleto o tiene un formato inválido.')
    if struct.unpack_from('<I',datos)[0]!=0:raise ValueError('El recorrido CARREC debe comenzar en el instante cero.')
    anterior=-1
    for offset in range(0,len(datos),32):
        tiempo=struct.unpack_from('<I',datos,offset)[0]
        posicion=struct.unpack_from('<3f',datos,offset+20)
        if tiempo<=anterior or not all(math.isfinite(v) for v in posicion):
            raise ValueError('El archivo Carrec tiene cuadros inválidos.')
        anterior=tiempo
    primer_punto=struct.unpack_from('<3f',datos,20)
    if math.dist(primer_punto[:2],inicio[:2])>2 or abs(primer_punto[2]-inicio[2])>2:
        raise ValueError('El recorrido Carrec empieza lejos del vehículo. No se copiará una grabación de otra ubicación.')
    if fin is not None and math.dist(struct.unpack_from('<3f',datos,len(datos)-12),fin)>2:
        raise ValueError('El final de la grabación CARREC no corresponde al final declarado en el MMS.')


def _validar_destinos(archivos,carpeta):
    """Rechaza un ID ya ocupado por otro contenido antes de escribir la misión."""
    for nombre,origen in archivos.items():
        if not nombre.startswith('Carrec/'):continue
        destino=Path(carpeta)/nombre
        for existente in (destino,destino.with_suffix('')):
            if existente.is_file() and existente.read_bytes()!=origen.read_bytes():
                raise ValueError('La carpeta destino ya contiene otra grabación con ese ID CARREC. '
                                 'Usa una carpeta propia para esta misión; no se mezclaron los archivos.')
        # El registro de recorridos de GTA es global, aunque SAMM use varias carpetas.
        carpeta_resuelta=Path(carpeta).resolve()
        base=next((p for p in (carpeta_resuelta,*carpeta_resuelta.parents)
                   if p.name.casefold()=='samm(stable)' and p.parent.name.casefold()=='modloader'),None)
        if base and base.is_dir():
            prefijo=Path(nombre).stem
            nombres={prefijo.casefold(),(prefijo+'.rrr').casefold()}
            huella=hashlib.sha256(origen.read_bytes()).digest()
            for otro in base.rglob(prefijo+'*'):
                if otro.is_file() and otro.name.casefold() in nombres and hashlib.sha256(otro.read_bytes()).digest()!=huella:
                    raise ValueError('Otra misión de SAMM utiliza ese ID CARREC con un recorrido distinto. '
                                     'Se bloqueó la entrega para evitar cargar una ruta ajena.')


def _escribir_atomico(destino,datos):
    """El mod solo ve el nombre definitivo después de escribir todos los bytes."""
    destino=Path(destino);destino.parent.mkdir(parents=True,exist_ok=True)
    temporal=None
    try:
        with tempfile.NamedTemporaryFile(prefix='.'+destino.name+'.',suffix='.pendiente',
                                         dir=destino.parent,delete=False) as archivo:
            temporal=Path(archivo.name);archivo.write(datos);archivo.flush();os.fsync(archivo.fileno())
        if temporal.read_bytes()!=datos:raise OSError('La copia de la misión no conservó todos los bytes.')
        temporal.replace(destino)
    finally:
        if temporal is not None:temporal.unlink(missing_ok=True)


def _manifiesto_actualizado(destino):
    """Selecciona el MMS elegido y conserva los demás datos de un paquete existente."""
    ruta=Path(destino).parent/'mission_pack.ini'
    if not ruta.exists():return manifiesto(destino)
    cfg=configparser.ConfigParser(interpolation=None);cfg.optionxform=str
    try:cfg.read(ruta,encoding='utf-8-sig')
    except (configparser.Error,UnicodeError) as error:
        raise ValueError('El mission_pack.ini de destino no se puede leer; no se modificó la misión.') from error
    if 'MISSION' not in cfg:cfg.add_section('MISSION')
    cfg['MISSION']['Current']=Path(destino).stem
    cfg['MISSION']['Version']='1.87'
    salida=io.StringIO();cfg.write(salida,space_around_delimiters=False)
    return salida.getvalue().replace('\n','\r\n').encode('utf-8')


def copiar_auxiliares(ruta,carpeta):
    import hashlib
    ruta,carpeta=Path(ruta),Path(carpeta)
    if not carpeta.is_dir():raise ValueError('Elige una carpeta de misión existente.')
    archivos=dependencias(ruta)
    _validar_destinos(archivos,carpeta)
    copiados=[]
    for nombre,p in archivos.items():
        if nombre==ruta.name:continue
        out=carpeta/nombre
        out.parent.mkdir(parents=True,exist_ok=True)
        if out.exists():
            if hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256(out.read_bytes()).digest():continue
            backup=out.with_name(out.name+'.'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.bak')
            shutil.copy2(out,backup)
        if p.resolve()!=out.resolve():shutil.copy2(p,out)
        copiados.append(nombre)
    return copiados


def manifiesto(ruta):
    ahora=datetime.now()
    return ('[MISSION]\nCurrent='+Path(ruta).stem+'\nVersion=1.87\nDate='+ahora.strftime('%d.%m.%Y')+
        '\nDateENG='+ahora.strftime('%m/%d/%Y')+'\nOwner=MMS-Director\n').encode('utf-8')


def zip_mision(ruta):
    salida=io.BytesIO()
    with zipfile.ZipFile(salida,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for nombre,p in dependencias(ruta).items():z.write(p,nombre)
        z.writestr('mission_pack.ini',manifiesto(ruta))
    return salida.getvalue()


def guardar_como(origen,destino,conservar_respaldo=True):
    origen,destino=Path(origen),Path(destino)
    archivos=dependencias(origen)
    _validar_destinos(archivos,destino.parent)
    destino.parent.mkdir(parents=True,exist_ok=True)
    # Leer y validar antes de cambiar nada. Los recursos se publican antes del MMS.
    entrega=[(destino if nombre==origen.name else destino.parent/nombre,p.read_bytes())
             for nombre,p in sorted(archivos.items(),key=lambda item:item[0]==origen.name)]
    entrega.append((destino.parent/'mission_pack.ini',_manifiesto_actualizado(destino)))
    anteriores={out:out.read_bytes() if out.is_file() else None for out,_ in entrega}
    marca=datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    cambiados=[]
    try:
        for out,datos in entrega:
            previo=anteriores[out]
            if previo==datos:continue
            if conservar_respaldo and previo is not None:
                _escribir_atomico(out.with_name(out.name+'.'+marca+'.bak'),previo)
            _escribir_atomico(out,datos);cambiados.append(out)
        dependencias(destino)
    except (OSError,ValueError,configparser.Error):
        for out in reversed(cambiados):
            if anteriores[out] is None:out.unlink(missing_ok=True)
            else:_escribir_atomico(out,anteriores[out])
        raise
    return destino


def instalar(ruta,gta):
    gta=Path(gta)
    if not any((gta/n).is_file() for n in ('gta.exe','gta_sa.exe')):
        raise ValueError('Configura la carpeta de GTA que contiene gta_sa.exe o gta.exe.')
    base=gta/'modloader/SAMM(Stable)'
    if not base.is_dir():raise ValueError('No se encontró SAMM(Stable) en esta instalación.')
    # Una carpeta independiente por exportación. Nunca sobrescribir las misiones del usuario.
    destino=base/Path(ruta).stem
    if destino.exists():raise ValueError('Esta misión ya está instalada. Genera otra versión para conservar la anterior.')
    archivos=dependencias(ruta)
    _validar_destinos(archivos,destino)
    guardar_como(ruta,destino/Path(ruta).name)
    return destino
