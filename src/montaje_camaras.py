"""Cortes de cámara nativos sin volver a programar las tareas de la escena.

Mission Maker 1.87 MissionCore.txt aplica OBJ_N después de completar su condición:
primero crea las entidades/acciones cuyo OBJ=N y después aplica su cámara. Por eso
una referencia al objetivo antiguo se remapea al ÚLTIMO fragmento nuevo de éste.
Los modos 6/7 de Loader/GameSet.txt usan 067C/0679 para anclar cámara a actor/coche.
Sus ORXYZ se pasan como attachedCamLookAt al motor; no son coordenadas del mundo.

Este módulo modifica sólo el texto MMS. No toca grabaciones CARREC ni audio, y no
afirma comprobar obstáculos de cámara o reproducción visual dentro del juego.
"""
from __future__ import annotations

import configparser
import io
import math
import re


INTERVALO_MS = 5000
VERSION = '1'


def _quitar_camara(campos):
    for clave in list(campos):
        if clave.startswith('PLA_CUM') or clave in ('CUM_ACTOR', 'CUM_VEH', 'CUM_RESTORE1', 'CUM_RESTORE2'):
            del campos[clave]


def _sujeto(config, vehiculo=False):
    prefijo = 'Vehicle_' if vehiculo else 'ACTOR_'
    candidatos = sorted((s for s in config if re.fullmatch(prefijo + r'\d+', s)),
        key=lambda s: int(s.split('_')[-1]))
    candidatos = [s for s in candidatos if config[s].get('OBJ', '0') == '0']
    if not candidatos:
        raise ValueError('No existe un sujeto inicial para el montaje de cámara.')
    seccion = candidatos[0]
    campos = config[seccion]
    posicion = tuple(float(campos[k]) for k in ('X', 'Y', 'Z'))
    angulo = float(campos.get('A', '0'))
    if not all(math.isfinite(v) for v in (*posicion, angulo)):
        raise ValueError('La posición del sujeto de cámara no es válida.')
    return seccion, posicion, angulo


def _camara(campos, config, indice, vehiculo=False):
    nombre, posicion, angulo = _sujeto(config, vehiculo)
    cantidad = sum(bool(re.fullmatch(r'ACTOR_\d+', s)) for s in config)
    grupo = max(0, cantidad - 1) * .55
    altura_techo = max((float(config[s].get('T_Z', '0')) for s in config
        if s.startswith('ACTION_A_') and config[s].get('Type') == '2'
        and config[s].get('SPHERE_TYPE') == '6'), default=0) if vehiculo else 0
    # Seguimiento, contexto del entorno y general moderado. Todos se trasladan
    # con el sujeto: no se quedan mirando el punto donde comenzó la caminata.
    perfiles = (
        ((.35, -5.9 if vehiculo else -4.4-grupo, 2.0 if vehiculo else 1.5), (0, 0, 1.0)),
        ((8+grupo, -7-grupo, 4.5), (1.8, 2.5, 1.0)),
        ((-10-grupo, -13-grupo, 8.0), (0, 0, 1.0)),
    )
    offset, objetivo = perfiles[indice % len(perfiles)]
    if altura_techo:
        offset = (offset[0], offset[1], offset[2]+altura_techo)
        objetivo = (objetivo[0], objetivo[1], objetivo[2]+altura_techo)
    rad = math.radians(angulo)

    def mundo(p):
        x, y, z = p
        return (posicion[0]+x*math.cos(rad)-y*math.sin(rad),
            posicion[1]+x*math.sin(rad)+y*math.cos(rad), posicion[2]+z)

    cam, punto = mundo(offset), mundo(objetivo)
    dx, dy, dz = (b-a for a, b in zip(cam, punto))
    _quitar_camara(campos)
    campos.update(PLA_CUM='1', PLA_CUM_MODE='7' if vehiculo else '6',
        PLA_CUM_ZOOM='70', CUM_ACTOR='1', CUM_VEH='1')
    campos['CUM_VEH' if vehiculo else 'CUM_ACTOR'] = nombre.split('_')[-1]
    for claves, valores in (
        (('PLA_CUM_X', 'PLA_CUM_Y', 'PLA_CUM_Z'), cam),
        (('PLA_CUM_PX', 'PLA_CUM_PY', 'PLA_CUM_PZ'), punto),
        (('PLA_CUM_OX', 'PLA_CUM_OY', 'PLA_CUM_OZ'), offset),
        (('PLA_CUM_ORX', 'PLA_CUM_ORY', 'PLA_CUM_ORZ'), objetivo),
    ):
        campos.update({k: f'{v:.6f}' for k, v in zip(claves, valores)})
    campos['PLA_CUM_inputX'] = str(180-math.degrees(math.atan2(dy, dx)) % 360)
    campos['PLA_CUM_inputY'] = str(math.degrees(math.atan2(dz, math.hypot(dx, dy))))


def _prefijo_entrada(config):
    """La pausa de 1 s comienza cuando realmente se ha entrado al coche."""
    espera = config['OBJ_1'] if 'OBJ_1' in config else {}
    pausa = config['OBJ_2'] if 'OBJ_2' in config else {}
    conduce = any(s.startswith('ACTION_V_') and config[s].get('Carrec')
        and config[s].get('OBJ') == '2' for s in config)
    return {1, 2} if (conduce and espera.get('Type') == '2'
        and espera.get('SPHERE_TYPE') == '5' and pausa.get('Type') == '6'
        and pausa.get('DIAL_TIME') == '1000') else set()


def aplicar_montaje(contenido: str, intervalo_ms: int = INTERVALO_MS) -> str:
    """Alterna el encuadre cada cinco segundos de la parte temporizada.

    Conserva todas las fronteras de tareas y diálogos, aunque no coincidan con un
    corte de cámara. La condición de entrada y su pausa de 1 s permanecen intactas;
    el reloj del montaje de conducción empieza después de esa pausa. Cada OBJ que
    se añade contiene sólo un temporizador y los ajustes anteriores: nunca duplica
    acciones. El resultado conserva las referencias y los hashes CARREC/MUSIC.

    Aplicar una segunda vez al mismo archivo no vuelve a segmentar sus objetivos.
    """
    if isinstance(intervalo_ms, bool) or not isinstance(intervalo_ms, int) or not 1000 <= intervalo_ms <= 60000:
        raise ValueError('El intervalo de montaje debe ser de 1000 a 60000 milisegundos.')
    config = configparser.ConfigParser(interpolation=None, strict=True)
    config.optionxform = str
    config.read_string(contenido)
    if 'MISSION' not in config or 'OBJ_0' not in config:
        raise ValueError('La misión no contiene la configuración inicial de cámara.')
    if config['MISSION'].get('AUTO_CAMERA_VERSION') == VERSION:
        return contenido
    indices = sorted(int(s[4:]) for s in config if re.fullmatch(r'OBJ_\d+', s))
    if indices != list(range(len(indices))):
        raise ValueError('Los objetivos de la misión no son consecutivos.')
    originales = {n: dict(config[f'OBJ_{n}']) for n in indices if n}
    protegidos = _prefijo_entrada(config)
    vehiculo = any(re.fullmatch(r'Vehicle_\d+', s) for s in config)
    actores = any(re.fullmatch(r'ACTOR_\d+', s) for s in config)
    # Durante la aproximación vemos al actor; el montaje del trayecto sigue el
    # vehículo. Las escenas autónomas también pueden tener cero actores.
    _camara(config['OBJ_0'], config, 0, vehiculo=vehiculo and (not actores or not protegidos))
    nuevos = []
    mapping = {0: 0}
    reloj = 0
    for indice, original in originales.items():
        if original.get('Type') != '6' or indice in protegidos:
            nuevos.append((dict(original), None))
            mapping[indice] = len(nuevos)
            continue
        try:
            restante = int(original['DIAL_TIME'])
        except (KeyError, ValueError) as error:
            raise ValueError('Un objetivo temporizado no tiene una duración válida.') from error
        if restante <= 0:
            raise ValueError('Un objetivo temporizado debe durar más de cero milisegundos.')
        while restante:
            duracion = min(restante, intervalo_ms-reloj % intervalo_ms)
            clon = dict(original)
            clon['DIAL_TIME'] = str(duracion)
            _quitar_camara(clon)
            # GAME_MUSIC en un objetivo añadido reiniciaría la banda sonora.
            # Las misiones de este compilador la configuran exclusivamente en0.
            if any(k == 'GAME_MUSIC' or k.startswith('MUSIC_') for k in original):
                raise ValueError('La música del montaje debe configurarse sólo en OBJ_0.')
            reloj += duracion
            nuevos.append((clon, reloj))
            restante -= duracion
        mapping[indice] = len(nuevos)
    if not reloj:
        raise ValueError('La misión no tiene una parte temporizada para montar cámaras.')
    # Las acciones se ejecutan DESPUÉS de completar el OBJ que referencian.
    # No remapear IDs de actores/vehículos u otros campos que contienen «OBJ».
    for seccion in config:
        if seccion.startswith('OBJ_') or 'OBJ' not in config[seccion]:
            continue
        try:
            anterior = int(config[seccion]['OBJ'])
            config[seccion]['OBJ'] = str(mapping[anterior])
        except (ValueError, KeyError) as error:
            raise ValueError('Una entidad o acción referencia un objetivo inexistente.') from error
    for nombre in list(config):
        if re.fullmatch(r'OBJ_[1-9]\d*', nombre): config.remove_section(nombre)
    for numero, (campos, momento) in enumerate(nuevos, 1):
        if protegidos and numero == mapping[2]:
            _camara(campos, config, 0, vehiculo=True)
        elif momento is not None and momento < reloj and momento % intervalo_ms == 0:
            _camara(campos, config, momento//intervalo_ms, vehiculo=vehiculo)
        config[f'OBJ_{numero}'] = campos
    config['MISSION'].update(SELECTED_OBJ=str(len(nuevos)), AUTO_CAMERA_VERSION=VERSION,
        AUTO_CAMERA_INTERVAL_MS=str(intervalo_ms), AUTO_CAMERA_SHOTS=str((reloj-1)//intervalo_ms+1))
    salida = io.StringIO()
    config.write(salida, space_around_delimiters=False)
    return salida.getvalue().replace('\n', '\r\n')
