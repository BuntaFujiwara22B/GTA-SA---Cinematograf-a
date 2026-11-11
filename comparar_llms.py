"""Comparación por API de seis LLM: planes JSON -> compilador MMS compartido."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import random
import re
import time
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
from evaluar_escenas import corpus, comprobar
from src.mvp_plan import PlanMVP, contexto_respaldo, validar_plan, _detalle_api
from src.mvp_mms import generar_mms
from src.propuesta_escena import completar_propuesta
from src.paths import ENV_FILE
from src.ubicaciones_escena import ubicaciones, elegir_ruta_vehiculo, puntos_entrada
from src.acceso_benchmark import generar, catalogo_gratuito

ROOT = Path(__file__).resolve().parent
BASE = ROOT / 'benchmark_llms'
MODELOS = {
    'gemini': 'gemini-3.5-flash',
    'ernie': 'baidu/ernie-5.5-flash-preview:free',
    'nemotron': 'nvidia/nemotron-3.5-super-vl:free',
    'dots': 'dots-studio/dots-3-note-preview:free',
    'cohere': 'cohere/north-mini-code:free',
    'liquid': 'liquid/lfm-3-1.7b:free',
}
NOMBRES = ['Gemini 3.5 Flash', 'ERNIE 5.5 Flash Preview', 'Nemotron 3.5 Super VL',
           'Dots3 Note Preview', 'North Mini Code', 'LFM 3 1.7B']
PROVEEDORES = {alias: 'google' if alias == 'gemini' else 'openrouter' for alias in MODELOS}
URL = 'https://openrouter.ai/api/v1/'


def guardar(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(ruta.suffix + '.tmp')
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding='utf-8')
    temporal.replace(ruta)


def huella(datos):
    return hashlib.sha256(json.dumps(datos, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def preparar():
    ruta = BASE / 'casos.json'
    if not ruta.exists():
        # Muestreo congelado sin consultar respuestas de ninguno de los seis modelos.
        casos = random.Random(20261111).sample(corpus(), 100)
        guardar(ruta, casos)
    casos = json.loads(ruta.read_text(encoding='utf-8'))
    if len(casos) != 100 or len({c['id'] for c in casos}) != 100:
        raise ValueError('El corpus debe contener exactamente 100 casos únicos.')
    prompts = BASE / 'prompts.json'
    if not prompts.exists():
        guardar(prompts, [dict(id=c['id'], system=contexto_respaldo(c['texto']),
                              user=c['texto']) for c in casos])
    mensajes = json.loads(prompts.read_text(encoding='utf-8'))
    if [(m['id'], m['user']) for m in mensajes] != [(c['id'], c['texto']) for c in casos]:
        raise ValueError('Los prompts no corresponden al corpus congelado.')
    return casos, mensajes


def solicitar(recurso, clave, datos=None):
    req = Request(URL + recurso, data=json.dumps(datos).encode() if datos else None,
                  headers={'Authorization': 'Bearer ' + clave,
                           'Content-Type': 'application/json', 'User-Agent': 'MMS-Benchmark/1.0'})
    with urlopen(req, timeout=120) as r:
        return json.load(r)


def descubrir():
    """Comprueba catálogos y cuotas, sin generar contenido ni mostrar secretos."""
    consultas = [
        ('groq', 'https://api.groq.com/openai/v1/models', 'GROQ_API_KEY'),
        ('google', 'https://generativelanguage.googleapis.com/v1beta/models', 'GEMINI_API_KEY'),
        ('openrouter', URL + 'models', 'OPENROUTER_API_KEY'),
    ]
    hallados = {}
    for proveedor, url, variable in consultas:
        clave = os.getenv(variable)
        if not clave:
            continue
        headers = {'x-goog-api-key': clave} if proveedor == 'google' else {'Authorization': 'Bearer ' + clave}
        try:
            with urlopen(Request(url, headers=headers), timeout=30) as r:
                datos = json.load(r)
            modelos = datos.get('data', datos.get('models', []))
            if proveedor == 'openrouter':
                modelos = [m for m in modelos if m['id'].endswith(':free') and
                           float(m['pricing']['prompt']) == float(m['pricing']['completion']) == 0]
            hallados[proveedor] = modelos
            print(proveedor + ':', ', '.join(m.get('id', m.get('name', '')) for m in modelos), flush=True)
        except HTTPError as e:
            print(proveedor, e.code, _detalle_api(e), flush=True)
        except Exception as e:
            print(proveedor, type(e).__name__, flush=True)
    guardar(BASE / 'descubrimiento.json', hallados)


def exportar(plan, texto):
    inicio, destino = (2100., -1700., 13.), (2100., -1696., 13.)
    if plan.ubicacion_id_sugerida:
        lugar = next(u for u in ubicaciones() if u['id'] == plan.ubicacion_id_sugerida)
        inicio, destino = tuple(lugar['posicion']), None
    if plan.accion in ('conducir_vehiculo', 'vehiculo_autonomo'):
        inicio, destino = puntos_entrada(elegir_ruta_vehiculo(identificador=plan.ruta_vehiculo_id))
    return generar_mms(actor_id=plan.actor_id_sugerido, actores_ids=plan.actores_ids_sugeridos,
        inicio=inicio, destino=destino, duracion=plan.duracion_sugerida,
        hora=plan.hora_sugerida, clima=plan.clima_id_sugerido, accion=plan.accion,
        animacion_sugerida=plan.animacion_sugerida, animar_actores=plan.animar_actores,
        tipo_movimiento=plan.tipo_movimiento, pasos=[p.model_dump() for p in plan.pasos],
        vehiculo_id=plan.vehiculo_id_sugerido, ruta_vehiculo_id=plan.ruta_vehiculo_id,
        vehiculo_en_movimiento=plan.vehiculo_en_movimiento, descripcion=texto)


def evaluar(caso, contenido, carpeta):
    resultado = dict(json_valido=False, mms_generado=False, correcto=False)
    try:
        # Algunos proveedores envuelven el JSON en Markdown: mismo tratamiento para todos.
        limpio = contenido.strip()
        if limpio.startswith('```') and limpio.endswith('```'):
            limpio = limpio.split('\n', 1)[1].rsplit('```', 1)[0].strip()
        crudo = PlanMVP.model_validate_json(limpio)
        resultado['json_valido'] = True
        resultado['plan_crudo'] = crudo.model_dump()
        plan = completar_propuesta(validar_plan(crudo, caso['texto']), caso['texto'])
        resultado['plan_final'] = plan.model_dump()
        if plan.es_valido:
            mms = exportar(plan, caso['texto'])
            # La plantilla ya contiene CRLF; no traducir otra vez en Windows.
            (carpeta / (caso['id'] + '.mms')).write_bytes(mms.encode('utf-8'))
            resultado.update(mms_generado=True, sha256_mms=hashlib.sha256(mms.encode()).hexdigest())
        comprobar(caso, plan)
        resultado['correcto'] = True
    except Exception as error:
        resultado['error_evaluacion'] = str(error)[:600]
    return resultado


def resumir(casos, firma):
    filas = []
    por_modelo = {}
    for (alias, modelo), nombre in zip(MODELOS.items(), NOMBRES):
        archivos = sorted((BASE / 'resultados' / alias).glob('escena_*.json'))
        registros = [json.loads(p.read_text(encoding='utf-8')) for p in archivos]
        registros = [r for r in registros if r['firma_experimento'] == firma]
        respuestas = [r for r in registros if r.get('respuesta_api')]
        por_modelo[alias] = {r['id']: r for r in respuestas}
        aciertos = sum(r.get('correcto', False) for r in respuestas)
        filas.append(dict(modelo=modelo, nombre=nombre, intentados=len(registros),
            respuestas=len(respuestas), correctos=aciertos,
            errores_api=len(registros)-len(respuestas),
            mms_generados=sum(r.get('mms_generado', False) for r in respuestas),
            porcentaje=100*aciertos/100 if len(respuestas) == 100 else None,
            porcentaje_parcial=100*aciertos/len(respuestas) if respuestas else None,
            costo_usd=sum((r.get('usage') or {}).get('cost', 0) or 0 for r in respuestas)))
    comunes = set.intersection(*(set(rs) for rs in por_modelo.values()))
    orden_comun = [c['id'] for c in casos if isinstance(c, dict) and c['id'] in comunes]
    for alias, fila in zip(MODELOS, filas):
        fila['casos_comunes'] = len(orden_comun)
        fila['correctos_comunes'] = sum(por_modelo[alias][i].get('correcto', False) for i in orden_comun)
        fila['porcentaje_comparable'] = 100*fila['correctos_comunes']/len(orden_comun) if orden_comun else None
    informe = dict(firma_experimento=firma, casos=len(casos), modelos=filas,
        casos_comunes=orden_comun, preliminar=len(orden_comun)<len(casos),
        alcance='Sistema LLM + contexto recuperado con borrador local + validación + compilador compartido. '
                'No mide generación directa de MMS por el LLM ni ejecución visual en GTA. '
                'Sin referencias visuales: mismo contexto textual para todos.',
        metrica='Exactitud: porcentaje de casos que cumplen todos los contratos. La gráfica compara '
                'exclusivamente los mismos IDs respondidos por los seis modelos; con menos de 100 es preliminar. '
                'Fallos JSON/semánticos cuentan como incorrectos. Errores API se registran aparte.')
    guardar(BASE / 'informe.json', informe)
    with (BASE / 'informe.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(filas[0]))
        writer.writeheader()
        writer.writerows(filas)
    return informe


def graficar(informe):
    os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.cache' / 'matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(16, 8), facecolor='#101418')
    ax.set_facecolor('#101418')
    filas = sorted(informe['modelos'], key=lambda f: -(f['porcentaje_comparable'] or 0))
    n = len(informe['casos_comunes'])
    for i, fila in enumerate(filas):
        valor = fila['porcentaje_comparable']
        ax.barh(i, valor or 0, color='#10d8ba' if fila['modelo'] == MODELOS['gemini'] else '#87979b', height=.68)
        etiqueta = f'{valor:.1f}% ({fila["correctos_comunes"]}/{n})' if valor is not None else f'Pendiente ({fila["respuestas"]}/100 respuestas)'
        ax.text((valor or 0)+1, i, etiqueta, color='white', va='center', fontweight='bold')
    ax.set_yticks(range(6), [f['nombre'] for f in filas], color='#dce1e4')
    ax.invert_yaxis()
    ax.set_xlim(0, 128)
    ax.set_xticks(range(0, 101, 20), [f'{v}%' for v in range(0, 101, 20)], color='#dce1e4')
    ax.xaxis.grid(True, color='#2b3339')
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.suptitle('Comparación de modelos para generar archivos .mms', color='white', fontsize=23, fontweight='bold', y=.97)
    etiqueta_muestra = f'{n} peticiones idénticas por modelo' if n else 'Aún no hay casos respondidos por los seis modelos'
    fig.text(.07, .88, etiqueta_muestra + (' · comparación preliminar (objetivo: 100)' if n < 100 else ''), color='#aebcc2', fontsize=15)
    fig.text(.07, .83, 'Cumplimiento de contratos del sistema · sin prueba visual en GTA', color='#6fd6c9', fontsize=13)
    fig.subplots_adjust(left=.23, right=.91, top=.75, bottom=.10)
    for extension in ('png', 'svg'):
        fig.savefig(BASE / f'comparacion.{extension}', dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ejecutar', action='store_true', help='Consume API; sin esta opción solo prepara el experimento.')
    parser.add_argument('--limite', type=int, default=100, help='Máximo de casos por modelo, 1..100; usar 1 para comprobar acceso.')
    parser.add_argument('--modelo', choices=list(MODELOS), action='append')
    parser.add_argument('--max-tokens', type=int, default=8192)
    parser.add_argument('--descubrir', action='store_true')
    parser.add_argument('--comprobar-acceso', action='store_true')
    parser.add_argument('--revalidar', action='store_true', help='Reevalúa respuestas guardadas sin consumir API; conserva su procedencia.')
    args = parser.parse_args()
    if not 1 <= args.limite <= 100 or args.max_tokens < 1:
        parser.error('Límite 1..100 y max-tokens positivo.')
    load_dotenv(ENV_FILE)
    if args.comprobar_acceso:
        from src.acceso_benchmark import probar
        acceso = BASE / 'prueba_acceso.json'
        previos = json.loads(acceso.read_text(encoding='utf-8')) if acceso.exists() else []
        guardar(acceso, probar(previos))
        return
    if args.descubrir:
        descubrir()
        return
    casos, prompts = preparar()
    fuentes = [Path(__file__), ROOT / 'evaluar_escenas.py', *sorted((ROOT / 'src').glob('*.py'))]
    config = dict(modelos=MODELOS, proveedores=PROVEEDORES, temperatura=.1, max_tokens=args.max_tokens,
                  fuentes_sha256={p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in fuentes},
                  corpus_sha256=huella(casos), prompts_sha256=huella(prompts))
    firma = huella(config)
    ruta_config = BASE / 'configuracion.json'
    if ruta_config.exists() and json.loads(ruta_config.read_text(encoding='utf-8')) != config:
        anterior_config = json.loads(ruta_config.read_text(encoding='utf-8'))
        if args.revalidar and any(anterior_config.get(k) != config[k] for k in
                                 ('modelos', 'proveedores', 'corpus_sha256', 'prompts_sha256', 'temperatura', 'max_tokens')):
            raise SystemExit('La revalidación permite cambiar código, no modelos, parámetros ni peticiones.')
        registros = (BASE / 'resultados').glob('*/*.json')
        if not args.revalidar and any(json.loads(p.read_text(encoding='utf-8')).get('respuesta_api') for p in registros):
            raise SystemExit('La configuración cambió. Conserve el experimento anterior en otra carpeta antes de continuar.')
        if args.revalidar:
            guardar(BASE / 'revisiones' / (huella(anterior_config) + '.json'), anterior_config)
    guardar(ruta_config, config)
    if args.revalidar:
        for alias in MODELOS:
            carpeta = BASE / 'resultados' / alias
            for caso in casos:
                ruta = carpeta / (caso['id'] + '.json')
                if not ruta.exists():
                    continue
                r = json.loads(ruta.read_text(encoding='utf-8'))
                if not r.get('respuesta_api'):
                    continue
                original = r['respuesta_original']
                if PROVEEDORES[alias] == 'google':
                    partes = (original.get('candidates') or [{}])[0].get('content', {}).get('parts', [])
                    contenido = ''.join(p.get('text', '') for p in partes if not p.get('thought'))
                else:
                    contenido = (original.get('choices') or [{}])[0].get('message', {}).get('content') or ''
                r.setdefault('revalidaciones', []).append(dict(
                    firma_anterior=r['firma_experimento'], correcto_anterior=r.get('correcto'),
                    fecha_utc=datetime.now(timezone.utc).isoformat(), sin_consulta_api=True))
                r.pop('error_evaluacion', None)
                r.update(evaluar(caso, contenido, carpeta), firma_experimento=firma)
                guardar(ruta, r)
    if args.ejecutar:
        if not os.getenv('OPENROUTER_API_KEY') or not os.getenv('GEMINI_API_KEY'):
            raise SystemExit('Se requieren GEMINI_API_KEY y OPENROUTER_API_KEY en .env.')
        catalogo = catalogo_gratuito()
        guardar(BASE / 'catalogo_api.json', catalogo)
        activos = []
        for alias, modelo in MODELOS.items():
            if args.modelo and alias not in args.modelo:
                continue
            if PROVEEDORES[alias] == 'openrouter' and modelo not in catalogo:
                print(f'{modelo}: no disponible con tarifa cero.', flush=True)
                continue
            activos.append(alias)
        # Intercalar modelos mantiene las muestras equilibradas si se agota una cuota.
        with ThreadPoolExecutor(max_workers=3) as executor:
            for caso, prompt in list(zip(casos, prompts))[:args.limite]:
                futuros = [(alias, executor.submit(ejecutar_caso, alias, caso, prompt, firma, args.max_tokens)) for alias in activos]
                for alias, futuro in futuros:
                    if not futuro.result():
                        activos.remove(alias)
                informe = resumir(casos, firma)
                graficar(informe)
                if not activos:
                    break
    informe = resumir(casos, firma)
    graficar(informe)
    print('Informe y gráfica: benchmark_llms/; comparación sobre los mismos casos respondidos por los seis modelos.')


def ejecutar_caso(alias, caso, prompt, firma, max_tokens):
    carpeta = BASE / 'resultados' / alias
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / (caso['id'] + '.json')
    if ruta.exists():
        anterior = json.loads(ruta.read_text(encoding='utf-8'))
        if anterior['firma_experimento'] != firma and anterior.get('respuesta_api'):
            raise ValueError('Respuesta de otro experimento: no se mezcla.')
        if anterior.get('respuesta_api'):
            return True
    r = dict(id=caso['id'], modelo=MODELOS[alias], proveedor=PROVEEDORES[alias], firma_experimento=firma,
             fecha_utc=datetime.now(timezone.utc).isoformat(), respuesta_api=False)
    inicio = time.monotonic()
    try:
        respuesta = generar(PROVEEDORES[alias], MODELOS[alias], prompt['system'], prompt['user'], max_tokens)
        r.update(respuesta_api=True, respuesta_original=respuesta['original'], usage=respuesta['usage'],
                 **evaluar(caso, respuesta['contenido'], carpeta))
    except HTTPError as error:
        detalle = re.sub(r'https://openrouter.ai/workspaces/\S+', '[panel privado de claves]', _detalle_api(error))
        r['error_api'] = dict(codigo=error.code, tipo='HTTPError', detalle=detalle)
    except Exception as error:
        r['error_api'] = dict(tipo=type(error).__name__)
    r['segundos'] = round(time.monotonic()-inicio, 3)
    guardar(ruta, r)
    print(f'{alias} {caso["id"]}: ' + ('correcto' if r.get('correcto') else 'fallo de contrato' if r['respuesta_api'] else f'error API {r["error_api"]}'), flush=True)
    return r['respuesta_api']


if __name__ == '__main__':
    main()
