"""Ablación real: mismas frases reservadas, con/sin modelo, hasta compilar el MMS.

No consume API, no modifica pesos ni ajusta umbrales. --exportar-ejemplos conserva
hasta tres escenas nuevas resueltas gracias al aprendizaje con su JSON de procedencia.
"""
import argparse
import configparser
from contextlib import nullcontext
import json
from pathlib import Path
from unittest.mock import patch

from entrenar_intenciones import cargar_corpus, escribir_json
from src.capacidades_escena import FAMILIAS, INTENCIONES_ENTRENADAS, opciones
from src.modelo_intenciones import predecir_intencion, _cargar, firma_modelo
from src.mvp_plan import plan_local, validar_plan
from src.propuesta_escena import completar_propuesta
from src.mvp_mms import generar_mms, exportar_escena

ROOT = Path(__file__).resolve().parent


def clip_esperado(intencion):
    import re
    titulo = INTENCIONES_ENTRENADAS[intencion]
    _, _, categoria, nombre = next(f for f in FAMILIAS if f[0] == titulo)
    return next(o for o in opciones() if (categoria is None or o['categoria'] == categoria)
                and re.search(nombre, o['anim'], re.I))


def datos_compilacion(plan, texto):
    return dict(actor_id=plan.actor_id_sugerido, actores_ids=plan.actores_ids_sugeridos,
        inicio=(2100., -1700., 13.), destino=None, duracion=plan.duracion_sugerida,
        hora=plan.hora_sugerida, clima=plan.clima_id_sugerido, accion=plan.accion,
        animacion_sugerida=plan.animacion_sugerida, animar_actores=plan.animar_actores,
        reproduccion=plan.reproduccion, descripcion=texto)


def comprobar(ejemplo, usar_modelo):
    contexto = nullcontext() if usar_modelo else patch(
        'src.capacidades_escena.candidata_aprendida', return_value=None)
    with contexto:
        p = validar_plan(plan_local(ejemplo['texto']), ejemplo['texto'])
        if p.es_valido:
            p = completar_propuesta(p, ejemplo['texto'])
    resultado = dict(aceptada=p.es_valido, accion=p.accion, fuente=p.fuente,
                     aprendizaje_supervisado=p.aprendizaje_supervisado,
                     animacion=p.animacion_sugerida, mms_compilado=False)
    if ejemplo['intencion'] == 'desconocido':
        # 'Desconocido' es ajeno a los 22 gestos; caminar sí puede tener otra vía válida.
        resultado['correcto'] = not (p.es_valido and p.accion == 'animacion')
        return resultado, p
    esperado = clip_esperado(ejemplo['intencion'])
    resultado['correcto'] = bool(p.es_valido and p.accion == 'animacion' and
                                 p.animacion_sugerida == esperado['id'])
    if not p.es_valido or p.accion != 'animacion':
        return resultado, p
    try:
        contenido = generar_mms(**datos_compilacion(p, ejemplo['texto']))
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.optionxform = str
        cfg.read_string(contenido)
        tareas = [cfg[s] for s in cfg.sections() if s.startswith('ACTION_A_') and
                  cfg[s].get('Type') == '3']
        resultado['mms_compilado'] = True
        resultado['correcto'] = resultado['correcto'] and bool(tareas) and all(
            a['ANIM'] == esperado['anim'] and a['IFP'] == esperado['lib'] for a in tareas)
    except (ValueError, KeyError) as error:
        resultado['correcto'] = False
        resultado['error_compilacion'] = str(error)
    return resultado, p


def evaluar(exportar=False):
    import hashlib
    from entrenar_intenciones import CORPUS
    _, partes = cargar_corpus()
    modelo = _cargar(firma_modelo())
    if modelo is None:
        raise ValueError('Primero ejecuta python entrenar_intenciones.py')
    if hashlib.sha256(CORPUS.read_bytes()).hexdigest() != modelo[0]['sha256_corpus']:
        raise ValueError('Corpus distinto al usado para entrenar; vuelve a entrenar.')
    resultados, exportados = [], []
    for e in partes['prueba']:
        anterior, _ = comprobar(e, False)
        actual, plan = comprobar(e, True)
        adicional = (e['intencion'] != 'desconocido' and actual['correcto'] and
                     not anterior['correcto'] and bool(plan.aprendizaje_supervisado))
        r = dict(id=e['id'], texto=e['texto'], esperado=e['intencion'],
                 sin_modelo=anterior, con_modelo=actual, resuelta_gracias_al_modelo=adicional)
        resultados.append(r)
        if exportar and adicional and len(exportados) < 3:
            ruta = exportar_escena(plan=plan.model_dump(), **datos_compilacion(plan, e['texto']))
            exportados.append(dict(texto=e['texto'], mms=str(ruta.relative_to(ROOT)),
                                   evidencia=str(ruta.with_suffix('.json').relative_to(ROOT))))
    positivos = [r for r in resultados if r['esperado'] != 'desconocido']
    negativos = [r for r in resultados if r['esperado'] == 'desconocido']
    informe = dict(modelo=modelo[0]['id_modelo'], sha256_pesos=modelo[0]['sha256_pesos'],
        alcance='Ablación de reglas + clasificación + validación + compilación en memoria. Sin API ni ejecución visual en GTA.',
        particion='prueba_reservada', total=len(resultados), gestos=len(positivos),
        fuera_del_clasificador=len(negativos),
        gestos_correctos_sin_modelo=sum(r['sin_modelo']['correcto'] for r in positivos),
        gestos_correctos_con_modelo=sum(r['con_modelo']['correcto'] for r in positivos),
        nuevas_peticiones_resueltas=sum(r['resuelta_gracias_al_modelo'] for r in resultados),
        regresiones=[r['id'] for r in resultados if r['sin_modelo']['correcto'] and not r['con_modelo']['correcto']],
        falsos_gestos_sin_modelo=sum(not r['sin_modelo']['correcto'] for r in negativos),
        falsos_gestos_con_modelo=sum(not r['con_modelo']['correcto'] for r in negativos),
        ejemplos_exportados=exportados, resultados=resultados)
    escribir_json(ROOT / 'evaluaciones/integracion_modelo_intenciones.json', informe)
    return informe


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exportar-ejemplos', action='store_true')
    args = parser.parse_args()
    informe = evaluar(args.exportar_ejemplos)
    print(json.dumps({k: v for k, v in informe.items() if k != 'resultados'}, ensure_ascii=False))
