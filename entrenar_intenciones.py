"""Entrena un clasificador supervisado real y exporta pesos portables, sin API.

Uso: python entrenar_intenciones.py
     python entrenar_intenciones.py --solo-evaluar
Los ejemplos de prueba nunca intervienen en fit, selección de C o umbrales.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import time

from src.modelo_intenciones import caracteristicas, normalizar, motivo_abstencion

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / 'datos_entrenamiento/intenciones_escena.json'
DESTINO = ROOT / 'models/intenciones'
INFORME = ROOT / 'evaluaciones/intenciones_supervisadas.json'


def cargar_corpus(ruta=None):
    ruta = Path(ruta) if ruta is not None else CORPUS
    datos = json.loads(ruta.read_text(encoding='utf-8'))
    ejemplos = datos['ejemplos']
    ids, textos, grupos = set(), set(), {}
    partes = {k: [] for k in ('entrenamiento', 'validacion', 'prueba')}
    clases = set(datos['clases'])
    for e in ejemplos:
        texto = ' '.join(normalizar(e['texto']).split())
        if e['id'] in ids or texto in textos:
            raise ValueError('ID o texto duplicado en el corpus: ' + e['id'])
        ids.add(e['id']); textos.add(texto)
        if e['intencion'] not in clases or e['particion'] not in partes:
            raise ValueError('Etiqueta o partición no reconocida: ' + e['id'])
        if e['grupo'] in grupos and grupos[e['grupo']] != e['particion']:
            raise ValueError('Fuga de grupo entre particiones: ' + e['grupo'])
        grupos[e['grupo']] = e['particion']
        partes[e['particion']].append(e)
    for nombre, filas in partes.items():
        if {e['intencion'] for e in filas} != clases:
            raise ValueError('Faltan clases en ' + nombre)
    return datos, partes


def variantes_entrenamiento(ejemplos):
    textos, etiquetas = [], []
    for e in ejemplos:
        for texto in (e['texto'], 'una persona ' + e['texto'] + ' durante veinte segundos',
                      'quiero una escena donde ' + e['texto'] + ' en la playa'):
            textos.append(texto); etiquetas.append(e['intencion'])
    return textos, etiquetas


def calcular_metricas(ejemplos, probabilidades, clases, umbral, margen, coberturas=None):
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
    import numpy as np
    reales = [e['intencion'] for e in ejemplos]
    predichas = [clases[int(i)] for i in probabilidades.argmax(axis=1)]
    filas, aceptados, correctos, falsos = [], 0, 0, 0
    negativos = sum(e['intencion'] == 'desconocido' for e in ejemplos)
    positivos = len(ejemplos) - negativos
    for n, (e, p, predicha) in enumerate(zip(ejemplos, probabilidades, predichas)):
        orden = np.sort(p)
        aceptada = (not motivo_abstencion(e['texto']) and predicha != 'desconocido' and
                    orden[-1] >= umbral and orden[-1] - orden[-2] >= margen and
                    (coberturas is None or coberturas[n] >= .12))
        aceptados += int(aceptada)
        correctos += int(aceptada and predicha == e['intencion'])
        falsos += int(aceptada and e['intencion'] == 'desconocido')
        filas.append(dict(id=e['id'], texto=e['texto'], esperado=e['intencion'],
                          predicho=predicha, aceptada=bool(aceptada),
                          puntuacion=round(float(orden[-1]), 6),
                          correcto=predicha == e['intencion']))
    return dict(total=len(ejemplos), exactitud=float(accuracy_score(reales, predichas)),
                f1_macro=float(f1_score(reales, predichas, average='macro', zero_division=0)),
                aceptados=aceptados, aceptados_correctos=correctos,
                precision_aceptados=correctos / aceptados if aceptados else None,
                cobertura_positivos=correctos / positivos if positivos else 0,
                negativos=negativos, falsos_positivos_desconocidos=falsos,
                tasa_falsos_positivos=falsos / negativos if negativos else 0,
                por_clase=classification_report(reales, predichas, labels=clases,
                    output_dict=True, zero_division=0),
                clases_matriz=list(clases),
                matriz_confusion=confusion_matrix(reales, predichas, labels=clases).tolist(),
                resultados=filas)


def elegir_umbral(ejemplos, probabilidades, clases, coberturas):
    """Máxima cobertura en validación con precisión >=97% y cero desconocidos aceptados."""
    import numpy as np
    mejor = None
    for umbral in np.arange(.15, .86, .05):
        for margen in (.05, .10, .15, .20, .30):
            resumen = calcular_metricas(ejemplos, probabilidades, clases, float(umbral), margen, coberturas)
            viable = (resumen['aceptados'] >= 3 and
                      resumen['precision_aceptados'] >= .97 and
                      resumen['falsos_positivos_desconocidos'] == 0)
            if viable:
                clave = (resumen['aceptados_correctos'], resumen['precision_aceptados'], float(umbral), margen)
                if mejor is None or clave > mejor[0]:
                    mejor = (clave, round(float(umbral), 3), margen, resumen)
    if mejor is None:
        raise RuntimeError('Validación insuficiente para activar el modelo de forma conservadora.')
    return mejor[1:]


def escribir_json(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix('.tmp')
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding='utf-8')
    temporal.replace(ruta)


def preparar_datos(usar_correcciones=False):
    """Las correcciones revisadas solo se agregan al entrenamiento, nunca a reservas."""
    datos, partes = cargar_corpus()
    resumen = dict(n_aprobadas=0, n_incorporadas=0, omitidas=[])
    if usar_correcciones:
        from src.correcciones_intenciones import obtener_aprobadas
        nuevas, resumen = obtener_aprobadas(datos)
        if not nuevas:
            raise ValueError('No hay correcciones aprobadas nuevas utilizables. Guarda y revisa etiquetas primero; '
                             'los duplicados y las frases reservadas no se incorporan.')
        partes['entrenamiento'] = partes['entrenamiento'] + nuevas
    textos, etiquetas = variantes_entrenamiento(partes['entrenamiento'])
    reservados = {' '.join(normalizar(e['texto']).split())
                  for parte in ('validacion', 'prueba') for e in partes[parte]}
    if any(' '.join(normalizar(t).split()) in reservados for t in textos):
        raise ValueError('El aumento de entrenamiento invade una partición reservada.')
    return datos, partes, textos, etiquetas, resumen


def firma_en(carpeta):
    return tuple((p.stat().st_mtime_ns, p.stat().st_size)
                 for p in (Path(carpeta) / 'metadata.json', Path(carpeta) / 'pesos.npz'))


def cargar_exportado(carpeta):
    from src.modelo_intenciones import _cargar_ruta
    return _cargar_ruta(str(Path(carpeta).resolve()), firma_en(carpeta))


def evaluar_particion(ejemplos, modelo):
    import numpy as np
    from src.modelo_intenciones import puntuaciones
    metadata = modelo[0]
    datos = [puntuaciones(e['texto'], modelo) for e in ejemplos]
    sin_vocabulario = np.zeros(len(metadata['clases']))
    sin_vocabulario[metadata['clases'].index('desconocido')] = 1.0
    probabilidades = np.array([p if p is not None else sin_vocabulario for p, _ in datos])
    return calcular_metricas(ejemplos, probabilidades, metadata['clases'],
        metadata['umbral'], metadata['margen_minimo'], [c for _, c in datos])


def activar_version(carpeta):
    """Promueve usando únicamente validación y guarda un respaldo antes de reemplazar."""
    carpeta = Path(carpeta).resolve()
    if carpeta == DESTINO.resolve():
        raise ValueError('La carpeta candidata ya es la activa.')
    candidata = cargar_exportado(carpeta)
    _, partes = cargar_corpus()
    huella_base = hashlib.sha256(CORPUS.read_bytes()).hexdigest()
    if candidata[0]['sha256_corpus'] != huella_base:
        raise ValueError('La candidata no corresponde al corpus base actual.')
    informe_candidato = None
    if (carpeta / 'informe.json').exists():
        informe_candidato = json.loads((carpeta / 'informe.json').read_text(encoding='utf-8'))
        if (informe_candidato.get('modelo') != candidata[0]['id_modelo'] or
                informe_candidato.get('sha256_pesos') != candidata[0]['sha256_pesos']):
            raise ValueError('El informe de la candidata no corresponde a sus pesos y metadatos.')
    evaluacion = evaluar_particion(partes['validacion'], candidata)
    if (evaluacion['aceptados'] < 3 or evaluacion['precision_aceptados'] < .97 or
            evaluacion['falsos_positivos_desconocidos']):
        raise ValueError('La candidata no supera la política de aceptación en validación.')
    presentes = [(DESTINO / n).exists() for n in ('metadata.json', 'pesos.npz')]
    if any(presentes) and not all(presentes):
        raise ValueError('El modelo activo está incompleto; conserva los archivos y repáralo antes de activar.')
    anterior, respaldo = None, None
    if all(presentes):
        anterior = evaluar_particion(partes['validacion'], cargar_exportado(DESTINO))
        if (evaluacion['aceptados_correctos'] < anterior['aceptados_correctos'] or
                evaluacion['f1_macro'] + 1e-12 < anterior['f1_macro']):
            raise ValueError('La candidata empeora cobertura correcta o F1 de validación; se conserva la activa.')
        respaldo = DESTINO / 'versiones' / ('respaldo-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        respaldo.mkdir(parents=True)
        for nombre in ('metadata.json', 'pesos.npz'):
            shutil.copy2(DESTINO / nombre, respaldo / nombre)
    DESTINO.mkdir(parents=True, exist_ok=True)
    try:
        for nombre in ('pesos.npz', 'metadata.json'):
            temporal = DESTINO / (nombre + '.pendiente')
            shutil.copy2(carpeta / nombre, temporal)
            temporal.replace(DESTINO / nombre)
        cargar_exportado(DESTINO)
    except (OSError, ValueError, KeyError):
        if respaldo:
            for nombre in ('pesos.npz', 'metadata.json'):
                shutil.copy2(respaldo / nombre, DESTINO / nombre)
        else:
            # No dejar un modelo inicial incompleto si la segunda copia falla.
            for nombre in ('pesos.npz', 'metadata.json'):
                (DESTINO / nombre).unlink(missing_ok=True)
        raise
    resultado = dict(modelo=candidata[0]['id_modelo'], respaldo=str(respaldo) if respaldo else None,
        criterio='Solo validación: precisión >=97%, cero desconocidos aceptados y cobertura/F1 sin empeorar.',
        aceptados_correctos_validacion=evaluacion['aceptados_correctos'],
        f1_validacion=evaluacion['f1_macro'])
    escribir_json(DESTINO / 'activacion.json', resultado)
    informe_activo = dict(informe_candidato or dict(
        modelo=candidata[0]['id_modelo'], sha256_pesos=candidata[0]['sha256_pesos'],
        sha256_corpus=huella_base, alcance='Versión sin informe de entrenamiento; solo se recalculó validación.'))
    informe_activo.update(estado='activa', activacion=resultado, validacion=evaluacion,
                         carpeta_version=str(carpeta))
    escribir_json(INFORME, informe_activo)
    if informe_candidato is not None:
        escribir_json(carpeta / 'informe.json', informe_activo)
    return resultado


def entrenar(usar_correcciones=False, activar=False, carpeta_version=None):
    import numpy as np
    import sklearn
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.feature_extraction.text import TfidfTransformer
    from sklearn.linear_model import LogisticRegression
    from threadpoolctl import threadpool_limits

    inicio = time.perf_counter()
    datos, partes, textos, etiquetas, correcciones = preparar_datos(usar_correcciones)
    vectorizador = DictVectorizer(dtype=float)
    frecuencias = vectorizador.fit_transform(caracteristicas(t) for t in textos)
    tfidf = TfidfTransformer(sublinear_tf=True)
    x_train = tfidf.fit_transform(frecuencias)
    # Únicamente entrenamiento define vocabulario e IDF.
    rasgos_val = [caracteristicas(e['texto']) for e in partes['validacion']]
    x_val = tfidf.transform(vectorizador.transform(rasgos_val))
    coberturas = [sum(k in vectorizador.vocabulary_ for k in f) / max(1, len(f)) for f in rasgos_val]
    candidatos, seleccionado = [], None
    with threadpool_limits(limits=1):
        for c in (1.0, 4.0, 12.0):
            clasificador = LogisticRegression(C=c, class_weight='balanced', max_iter=1200,
                                              random_state=42, solver='lbfgs')
            clasificador.fit(x_train, etiquetas)
            p_val = clasificador.predict_proba(x_val)
            try:
                umbral, margen, resumen = elegir_umbral(partes['validacion'], p_val,
                                                        list(clasificador.classes_), coberturas)
            except RuntimeError:
                candidatos.append(dict(C=c, descartado='No supera los criterios en validación.'))
                continue
            candidatos.append(dict(C=c, f1_macro=resumen['f1_macro'], umbral=umbral,
                                   margen=margen, precision_aceptados=resumen['precision_aceptados'],
                                   cobertura_positivos=resumen['cobertura_positivos']))
            clave = (resumen['cobertura_positivos'], resumen['f1_macro'])
            if seleccionado is None or clave > seleccionado[0]:
                seleccionado = (clave, clasificador, umbral, margen, resumen)
    if seleccionado is None:
        raise RuntimeError('Ninguna configuración superó los criterios en validación; se conserva la activa.')
    _, clasificador, umbral, margen, validacion = seleccionado
    if int(clasificador.n_iter_.max()) >= 1200:
        raise RuntimeError('El optimizador no convergió; no se publican pesos incompletos.')
    instante = datetime.now(timezone.utc)
    huella = hashlib.sha256(CORPUS.read_bytes()).hexdigest()
    id_version = 'intenciones-gta-supervisado-v2-' + instante.strftime('%Y%m%dT%H%M%S%fZ')
    carpeta_version = Path(carpeta_version) if carpeta_version else DESTINO / 'versiones' / id_version
    if carpeta_version.resolve() == DESTINO.resolve():
        raise ValueError('Entrena en una versión separada; usa --activar para promoverla después.')
    carpeta_version.mkdir(parents=True, exist_ok=False)
    pesos = carpeta_version / 'pesos.npz'
    temporal = carpeta_version / 'pesos.tmp.npz'
    np.savez_compressed(temporal, idf=tfidf.idf_, coef=clasificador.coef_,
                        intercept=clasificador.intercept_)
    temporal.replace(pesos)
    huella_entrenamiento = hashlib.sha256(json.dumps(partes['entrenamiento'],
        ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
    metadata = dict(id_modelo=id_version,
        algoritmo='regresion_logistica_multiclase_tfidf', version_caracteristicas=1,
        clases=list(clasificador.classes_), vocabulario=vectorizador.vocabulary_,
        umbral=umbral, margen_minimo=margen, cobertura_minima=.12,
        C=clasificador.C, semilla=42, sklearn_version=sklearn.__version__,
        origen_datos=datos.get('origen', 'curacion_manual_asistida'),
        sha256_corpus=huella, sha256_pesos=hashlib.sha256(pesos.read_bytes()).hexdigest(),
        sha256_entrenamiento=huella_entrenamiento, correcciones_revisadas=correcciones,
        entrenado_utc=instante.isoformat(),
        particiones={k: len(v) for k, v in partes.items()},
        ejemplos_ajuste=len(textos), caracteristicas=len(vectorizador.vocabulary_),
        iteraciones=int(clasificador.n_iter_.max()),
        alcance='Un gesto por petición; 22 gestos y desconocido. No amplía las mecánicas del compilador.')
    escribir_json(carpeta_version / 'metadata.json', metadata)
    snapshot = dict(datos, ejemplos=[e for filas in partes.values() for e in filas])
    escribir_json(carpeta_version / 'corpus_utilizado.json', snapshot)
    from src.modelo_intenciones import puntuaciones
    exportado = cargar_exportado(carpeta_version)
    # Paridad sklearn/exportación en validación antes de evaluar la prueba reservada.
    p_exportadas = np.array([puntuaciones(e['texto'], exportado)[0] for e in partes['validacion']])
    diferencia = float(np.max(np.abs(p_exportadas - clasificador.predict_proba(x_val))))
    if diferencia > 1e-10:
        raise RuntimeError('La exportación no conserva las predicciones de sklearn.')
    informe = evaluar_guardado(partes, metadata, carpeta_version)
    informe.update(segundos_entrenamiento=round(time.perf_counter()-inicio, 3),
        seleccion_solo_validacion=candidatos, max_error_paridad_exportacion=diferencia,
        validacion=validacion, carpeta_version=str(carpeta_version),
        correcciones_revisadas=correcciones, estado='candidata')
    escribir_json(carpeta_version / 'informe.json', informe)
    if activar:
        informe['activacion'] = activar_version(carpeta_version)
        informe['estado'] = 'activa'
        escribir_json(INFORME, informe)
        escribir_json(carpeta_version / 'informe.json', informe)
    escribir_json(ROOT / 'evaluaciones/intenciones_ultimo_entrenamiento.json', informe)
    return informe


def evaluar_guardado(partes=None, metadata=None, carpeta_modelo=None):
    if partes is None:
        _, partes = cargar_corpus()
    modelo = cargar_exportado(carpeta_modelo or DESTINO)
    if modelo is None:
        raise ValueError('Primero ejecuta python entrenar_intenciones.py')
    metadata = metadata or modelo[0]
    if hashlib.sha256(CORPUS.read_bytes()).hexdigest() != metadata['sha256_corpus']:
        raise ValueError('El corpus cambió desde el entrenamiento; vuelve a entrenar.')
    prueba = evaluar_particion(partes['prueba'], modelo)
    return dict(modelo=metadata['id_modelo'], sha256_pesos=metadata['sha256_pesos'],
        sha256_corpus=metadata['sha256_corpus'], particiones=metadata['particiones'],
        alcance='Métricas reales de este corpus curado, no peticiones de usuarios ni validación visual en GTA.',
        metodologia='Vocabulario/IDF/pesos solo en entrenamiento; C y umbrales solo en validación; '
            'prueba histórica congelada, ya observada en versiones anteriores. No decide activación.',
        limitaciones=['Corpus pequeño redactado con asistencia de IA y sin validación humana independiente.',
            'Separación por texto y grupo; las expresiones pueden compartir vocabulario entre particiones.',
            'Puntuaciones softmax sin calibración probabilística externa.',
            'Los desconocidos y la ambigüedad no se cubren exhaustivamente.'], prueba=prueba)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--solo-evaluar', action='store_true')
    parser.add_argument('--usar-correcciones', action='store_true',
                        help='Añade solo correcciones aprobadas, sin duplicados ni frases reservadas.')
    parser.add_argument('--activar', action='store_true',
                        help='Activa la versión entrenada solo si supera la política de validación.')
    parser.add_argument('--activar-version', type=Path,
                        help='Activa una carpeta de versión ya entrenada, evaluando solo validación.')
    args = parser.parse_args()
    if args.activar_version:
        if args.solo_evaluar or args.usar_correcciones or args.activar:
            parser.error('--activar-version no se combina con otras operaciones.')
        print(json.dumps(activar_version(args.activar_version), ensure_ascii=False))
        return
    if args.solo_evaluar:
        if args.usar_correcciones or args.activar:
            parser.error('--solo-evaluar no entrena ni activa versiones.')
        informe = evaluar_guardado()
        escribir_json(ROOT / 'evaluaciones/intenciones_reevaluacion.json', informe)
    else:
        informe = entrenar(usar_correcciones=args.usar_correcciones, activar=args.activar)
    p = informe['prueba']
    print(json.dumps(dict(modelo=informe['modelo'], prueba=p['total'],
        exactitud=p['exactitud'], f1_macro=p['f1_macro'], aceptados=p['aceptados'],
        precision_aceptados=p['precision_aceptados'], cobertura_positivos=p['cobertura_positivos'],
        falsos_positivos_desconocidos=p['falsos_positivos_desconocidos'],
        estado=informe.get('estado', 'evaluacion'), carpeta_version=informe.get('carpeta_version')), ensure_ascii=False))


if __name__ == '__main__':
    main()
