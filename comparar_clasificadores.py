"""Compara seis clasificadores de texto con datos reales y sin consultar APIs.

Los parámetros están prefijados; las puntuaciones de prueba son descriptivas y no
deciden el modelo activo. La curva de aprendizaje utiliza solo entrenamiento y
validación. python comparar_clasificadores.py --sin-graficas evita matplotlib.
"""
import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import platform
import random
import statistics
import time
import warnings

from entrenar_intenciones import cargar_corpus, variantes_entrenamiento
from src.modelo_intenciones import caracteristicas

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / 'datos_entrenamiento/intenciones_escena.json'
SALIDA = ROOT / 'evaluaciones'
FRACCIONES = (.25, .50, .75, 1.0)
SEMILLAS = (42, 43, 44)


def huellas_modelo():
    return {nombre: hashlib.sha256((ROOT / 'models/intenciones' / nombre).read_bytes()).hexdigest()
            if (ROOT / 'models/intenciones' / nombre).exists() else None
            for nombre in ('metadata.json', 'pesos.npz')}


def clasificadores():
    from sklearn.linear_model import LogisticRegression, RidgeClassifier, SGDClassifier
    from sklearn.naive_bayes import ComplementNB, MultinomialNB
    from sklearn.svm import LinearSVC
    return {
        'Regresión logística': LogisticRegression(C=12, class_weight='balanced',
            max_iter=1200, random_state=42, solver='lbfgs'),
        'SVM lineal': LinearSVC(C=1, class_weight='balanced', random_state=42, max_iter=4000),
        'Naive Bayes multinomial': MultinomialNB(alpha=1),
        'Naive Bayes complementario': ComplementNB(alpha=1),
        'Ridge': RidgeClassifier(alpha=1, class_weight='balanced'),
        'SGD logístico': SGDClassifier(loss='log_loss', alpha=.0001,
            class_weight='balanced', random_state=42, max_iter=2000, tol=1e-4),
    }


def ajustar_representacion(ejemplos_entrenamiento):
    """El vocabulario y el IDF nunca se ajustan con validación o prueba."""
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.feature_extraction.text import TfidfTransformer
    textos, etiquetas = variantes_entrenamiento(ejemplos_entrenamiento)
    vectorizador = DictVectorizer(dtype=float)
    conteos = vectorizador.fit_transform(caracteristicas(t) for t in textos)
    tfidf = TfidfTransformer(sublinear_tf=True)
    matriz = tfidf.fit_transform(conteos)
    return vectorizador, tfidf, matriz, etiquetas


def transformar(vectorizador, tfidf, textos):
    return tfidf.transform(vectorizador.transform(caracteristicas(t) for t in textos))


def metricas(ejemplos, predichas, clases):
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
    reales = [e['intencion'] for e in ejemplos]
    return dict(total=len(ejemplos), exactitud=float(accuracy_score(reales, predichas)),
        f1_macro=float(f1_score(reales, predichas, labels=clases, average='macro', zero_division=0)),
        por_clase=classification_report(reales, predichas, labels=clases,
            output_dict=True, zero_division=0),
        clases_matriz=clases,
        matriz_confusion=confusion_matrix(reales, predichas, labels=clases).tolist(),
        resultados=[dict(id=e['id'], esperado=e['intencion'], predicho=str(p),
            correcto=e['intencion'] == p) for e, p in zip(ejemplos, predichas)])


def medir_latencia(estimador, vectorizador, tfidf, ejemplos, repeticiones=30):
    """Lote de una petición, incluye texto→rasgos→TF-IDF→predict; modelo ya cargado."""
    import numpy as np
    if repeticiones < 3 or not ejemplos:
        raise ValueError('Se requieren ejemplos y al menos tres repeticiones.')
    for e in ejemplos[:3]:
        estimador.predict(transformar(vectorizador, tfidf, [e['texto']]))
    tiempos = []
    for i in range(repeticiones):
        texto = ejemplos[i % len(ejemplos)]['texto']
        inicio = time.perf_counter_ns()
        estimador.predict(transformar(vectorizador, tfidf, [texto]))
        tiempos.append((time.perf_counter_ns() - inicio) / 1e6)
    return dict(mediana_ms=float(statistics.median(tiempos)),
        p95_ms=float(np.percentile(tiempos, 95)), repeticiones=repeticiones,
        alcance='Lote 1; extracción, TF-IDF y predict con modelo cargado. No incluye GTA, UI ni red.')


def seleccionar_grupos(ejemplos, fraccion, semilla):
    """Selecciona grupos base por clase ANTES de crear variantes de contexto."""
    if not 0 < fraccion <= 1:
        raise ValueError('Fracción fuera de rango.')
    por_clase = defaultdict(set)
    clase_grupo = {}
    for e in ejemplos:
        if e['grupo'] in clase_grupo and clase_grupo[e['grupo']] != e['intencion']:
            raise ValueError('Un grupo de la curva contiene etiquetas distintas.')
        clase_grupo[e['grupo']] = e['intencion']
        por_clase[e['intencion']].add(e['grupo'])
    rng = random.Random(semilla)
    seleccionados = set()
    for clase in sorted(por_clase):
        grupos = sorted(por_clase[clase])
        seleccionados.update(rng.sample(grupos, max(1, math.ceil(len(grupos) * fraccion))))
    return [e for e in ejemplos if e['grupo'] in seleccionados]


def curva_aprendizaje(entrenamiento, validacion, clases):
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import f1_score
    puntos = []
    for fraccion in FRACCIONES:
        repeticiones = []
        for semilla in SEMILLAS:
            muestra = seleccionar_grupos(entrenamiento, fraccion, semilla)
            vectorizador, tfidf, matriz, etiquetas = ajustar_representacion(muestra)
            estimador = LogisticRegression(C=12, class_weight='balanced', max_iter=1200,
                random_state=42, solver='lbfgs')
            estimador.fit(matriz, etiquetas)
            x_val = transformar(vectorizador, tfidf, [e['texto'] for e in validacion])
            repeticiones.append(dict(semilla=semilla, ejemplos_base=len(muestra),
                ejemplos_ajuste=len(etiquetas), caracteristicas=len(vectorizador.vocabulary_),
                f1_entrenamiento=float(f1_score(etiquetas, estimador.predict(matriz),
                    labels=clases, average='macro', zero_division=0)),
                f1_validacion=float(f1_score([e['intencion'] for e in validacion],
                    estimador.predict(x_val), labels=clases, average='macro', zero_division=0))))
        puntos.append(dict(fraccion=fraccion, ejemplos_base=repeticiones[0]['ejemplos_base'],
            f1_entrenamiento_media=statistics.mean(r['f1_entrenamiento'] for r in repeticiones),
            f1_entrenamiento_std=statistics.pstdev(r['f1_entrenamiento'] for r in repeticiones),
            f1_validacion_media=statistics.mean(r['f1_validacion'] for r in repeticiones),
            f1_validacion_std=statistics.pstdev(r['f1_validacion'] for r in repeticiones),
            repeticiones=repeticiones))
    return dict(clasificador='Regresión logística C=12', particion_evaluacion='validacion',
        alcance='Muestreo estratificado de grupos antes del aumento; tres semillas; ningún uso de prueba.',
        puntos=puntos)


def guardar_informe(informe, destino):
    destino.mkdir(parents=True, exist_ok=True)
    (destino / 'comparacion_clasificadores.json').write_text(
        json.dumps(informe, ensure_ascii=False, indent=2), encoding='utf-8')
    with (destino / 'comparacion_clasificadores.csv').open('w', encoding='utf-8-sig', newline='') as archivo:
        columnas = ('modelo', 'validacion_exactitud', 'validacion_f1_macro', 'prueba_exactitud',
            'prueba_f1_macro', 'segundos_ajuste', 'latencia_mediana_ms', 'latencia_p95_ms')
        escritor = csv.DictWriter(archivo, fieldnames=columnas)
        escritor.writeheader()
        for r in informe['clasificadores']:
            escritor.writerow(dict(modelo=r['nombre'], validacion_exactitud=r['validacion']['exactitud'],
                validacion_f1_macro=r['validacion']['f1_macro'], prueba_exactitud=r['prueba']['exactitud'],
                prueba_f1_macro=r['prueba']['f1_macro'], segundos_ajuste=r['segundos_ajuste'],
                latencia_mediana_ms=r['latencia']['mediana_ms'], latencia_p95_ms=r['latencia']['p95_ms']))


def generar_graficas(informe, destino):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    destino.mkdir(parents=True, exist_ok=True)
    nombres = [r['nombre'] for r in informe['clasificadores']]
    colores = ['#3b82f6', '#14b8a6']
    archivos = []

    def guardar(fig, nombre, rect=(0, .04, 1, 1)):
        fig.text(.01, .01, 'Datos medidos · Corpus artificial asistido · Sin evaluación visual en GTA',
                 fontsize=8, color='#475569')
        fig.tight_layout(rect=rect)
        for extension in ('png', 'svg', 'pdf'):
            ruta = destino / f'{nombre}.{extension}'
            fig.savefig(ruta, dpi=180, bbox_inches='tight')
            archivos.append(str(ruta.relative_to(ROOT)) if ruta.is_relative_to(ROOT) else str(ruta))
        plt.close(fig)

    fig, ejes = plt.subplots(1, 2, figsize=(13, 5.4), sharey=True)
    y = np.arange(len(nombres))
    for eje, particion, titulo in zip(ejes, ('validacion', 'prueba'),
                                    ('Validación: 84 frases', 'Prueba histórica: 112 frases')):
        for offset, metrica, etiqueta, color in ((-.19, 'exactitud', 'Exactitud', colores[0]),
                                                (.19, 'f1_macro', 'F1 macro', colores[1])):
            valores = [100 * r[particion][metrica] for r in informe['clasificadores']]
            barras = eje.barh(y + offset, valores, height=.34, color=color, label=etiqueta)
            eje.bar_label(barras, fmt='%.1f', padding=3, fontsize=8)
        eje.set(xlim=(0, 108), xlabel='Puntuación (%)', title=titulo, yticks=y, yticklabels=nombres)
        eje.grid(axis='x', alpha=.2)
    ejes[0].invert_yaxis()
    handles, etiquetas = ejes[1].get_legend_handles_labels()
    fig.legend(handles, etiquetas, loc='lower center', bbox_to_anchor=(.5, .025),
               ncol=2, frameon=False)
    fig.suptitle('Comparación real de seis clasificadores de intención')
    guardar(fig, 'calidad_clasificadores', rect=(0, .10, 1, 1))

    fig, eje = plt.subplots(figsize=(10, 5))
    for offset, metrica, etiqueta, color in ((-.19, 'mediana_ms', 'Mediana', colores[0]),
                                            (.19, 'p95_ms', 'Percentil 95', colores[1])):
        valores = [r['latencia'][metrica] for r in informe['clasificadores']]
        barras = eje.barh(y + offset, valores, height=.34, color=color, label=etiqueta)
        eje.bar_label(barras, fmt='%.3f', padding=3, fontsize=8)
    eje.set(yticks=y, yticklabels=nombres, xlabel='Milisegundos por petición (lote 1)',
            title='Latencia medida: texto → rasgos → TF-IDF → clasificación')
    eje.invert_yaxis(); eje.legend(); eje.grid(axis='x', alpha=.2)
    guardar(fig, 'latencia_clasificadores')

    fig, eje = plt.subplots(figsize=(9, 5))
    puntos = informe['curva_aprendizaje']['puntos']
    x = [p['ejemplos_base'] for p in puntos]
    for prefijo, etiqueta, color in (('f1_entrenamiento', 'Entrenamiento', colores[0]),
                                     ('f1_validacion', 'Validación', colores[1])):
        media = np.array([p[prefijo + '_media'] * 100 for p in puntos])
        std = np.array([p[prefijo + '_std'] * 100 for p in puntos])
        eje.plot(x, media, 'o-', label=etiqueta, color=color)
        eje.fill_between(x, media - std, media + std, color=color, alpha=.15)
    eje.set(xlabel='Frases base de entrenamiento antes del aumento', ylabel='F1 macro (%)',
            ylim=(0, 103), title='Curva de aprendizaje: regresión logística, tres semillas')
    eje.grid(alpha=.2); eje.legend()
    guardar(fig, 'curva_aprendizaje_intenciones')
    return archivos


def comparar(graficas=True, destino=SALIDA):
    import numpy as np
    import sklearn
    from threadpoolctl import threadpool_limits
    if graficas and importlib.util.find_spec('matplotlib') is None:
        raise RuntimeError('Instala requirements-analysis.txt o utiliza --sin-graficas.')
    antes = huellas_modelo()
    datos, partes = cargar_corpus(CORPUS)
    clases = sorted(datos['clases'])
    inicio = time.perf_counter()
    vectorizador, tfidf, x_train, etiquetas = ajustar_representacion(partes['entrenamiento'])
    segundos_representacion = time.perf_counter() - inicio
    x_val = transformar(vectorizador, tfidf, [e['texto'] for e in partes['validacion']])
    resultados, ajustados = [], []
    with threadpool_limits(limits=1):
        # Primera fase: entrenamiento y validación para TODOS; todavía sin evaluar prueba.
        for nombre, estimador in clasificadores().items():
            with warnings.catch_warnings(record=True) as avisos:
                warnings.simplefilter('always')
                inicio = time.perf_counter()
                estimador.fit(x_train, etiquetas)
                segundos = time.perf_counter() - inicio
            resultados.append(dict(nombre=nombre, parametros=estimador.get_params(),
                segundos_ajuste=segundos,
                validacion=metricas(partes['validacion'], estimador.predict(x_val), clases),
                latencia=medir_latencia(estimador, vectorizador, tfidf, partes['validacion']),
                advertencias=[dict(tipo=type(a.message).__name__, mensaje=str(a.message)) for a in avisos]))
            ajustados.append(estimador)
        curva = curva_aprendizaje(partes['entrenamiento'], partes['validacion'], clases)
        # Parámetros y candidatos ya congelados; prueba solo describe esos seis ajustes.
        x_test = transformar(vectorizador, tfidf, [e['texto'] for e in partes['prueba']])
        for resultado, estimador in zip(resultados, ajustados):
            resultado['prueba'] = metricas(partes['prueba'], estimador.predict(x_test), clases)
    despues = huellas_modelo()
    if antes != despues:
        raise RuntimeError('El modelo activo cambió durante la comparación. Repite sin entrenar en paralelo.')
    informe = dict(fecha_utc=datetime.now(timezone.utc).isoformat(),
        origen='benchmark_real_local_sin_API', sha256_corpus=hashlib.sha256(CORPUS.read_bytes()).hexdigest(),
        versiones=dict(python=platform.python_version(), sklearn=sklearn.__version__, numpy=np.__version__),
        plataforma=dict(sistema=platform.system(), arquitectura=platform.machine(), procesador=platform.processor()),
        semilla=42, hilos_blas=1, particiones={k: len(v) for k, v in partes.items()},
        ejemplos_ajuste=len(etiquetas), caracteristicas=len(vectorizador.vocabulary_),
        segundos_representacion=segundos_representacion,
        alcance='Clasificación textual sin política de abstención, compilación MMS ni reproducción en GTA.',
        metodologia='Parámetros prefijados. Misma representación y particiones. Vocabulario e IDF solo en entrenamiento. Ninguna selección por prueba.',
        limitaciones=['Corpus pequeño, artificial y redactado con asistencia de IA.',
            'Prueba histórica de 112 ejemplos ya utilizada previamente; no es una nueva evaluación externa.',
            'No compara Gemini, Qwen ni otros LLM; compara seis clasificadores supervisados de intención.',
            'Una medición de entrenamiento por algoritmo; latencia de modelo caliente en este equipo.',
            'Los parámetros no son una búsqueda exhaustiva optimizada por algoritmo.',
            'No se activa ni se sustituye ningún modelo de la aplicación.'],
        modelo_activo_antes=antes, modelo_activo_despues=despues, modelo_activo_sin_cambios=antes == despues,
        clasificadores=resultados, curva_aprendizaje=curva, graficas=[])
    if graficas:
        informe['graficas'] = generar_graficas(informe, destino / 'graficas')
    guardar_informe(informe, destino)
    return informe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sin-graficas', action='store_true')
    parser.add_argument('--solo-graficas', action='store_true',
                        help='Dibuja el informe guardado sin repetir el entrenamiento.')
    args = parser.parse_args()
    if args.solo_graficas:
        ruta = SALIDA / 'comparacion_clasificadores.json'
        informe = json.loads(ruta.read_text(encoding='utf-8'))
        informe['graficas'] = generar_graficas(informe, SALIDA / 'graficas')
        guardar_informe(informe, SALIDA)
    else:
        informe = comparar(graficas=not args.sin_graficas)
    print(json.dumps(dict(modelo_activo_sin_cambios=informe['modelo_activo_sin_cambios'],
        resultados=[dict(modelo=r['nombre'], f1_validacion=r['validacion']['f1_macro'],
            f1_prueba=r['prueba']['f1_macro'], exactitud_prueba=r['prueba']['exactitud'])
            for r in informe['clasificadores']], graficas=informe['graficas']), ensure_ascii=False))


if __name__ == '__main__':
    main()
