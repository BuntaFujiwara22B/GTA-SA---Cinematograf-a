# Modelo supervisado de intenciones de escena

MMS-Director incorpora un clasificador entrenado con frases etiquetadas en español. Aprende a relacionar la descripción de un gesto con una de 22 intenciones de animación y una clase `desconocido`. Sus predicciones pueden seleccionar un clip existente, preparar el plan y llegar al archivo `.mms` que genera la aplicación.

Es **aprendizaje supervisado de clasificación de texto** mediante TF-IDF y regresión logística multiclase. El entrenamiento ajusta coeficientes numéricos a partir de ejemplos; agregar sinónimos a una lista de reglas no constituye este entrenamiento. El vocabulario y las ponderaciones IDF también se obtienen de la partición de entrenamiento.

Este componente interpreta texto. No es un modelo de visión, no entrena CLIP y no realiza fine-tuning de Gemini. Gemini, Qwen, CLIP, los catálogos y las validaciones conservan sus funciones en las otras partes del sistema.

## Corpus base y particiones históricas

El corpus base está en [`datos_entrenamiento/intenciones_escena.json`](datos_entrenamiento/intenciones_escena.json). Contiene 548 ejemplos, con estas particiones preasignadas:

| Partición | Ejemplos | Uso |
| --- | ---: | --- |
| Entrenamiento | 352 | Aprender vocabulario, IDF y coeficientes del clasificador. |
| Validación | 84 | Seleccionar regularización y umbrales de aceptación. |
| Prueba histórica | 112 | Comparar descriptivamente versiones; ya se observó al evaluar la primera versión. No decide activación. |

Cada una de las 22 intenciones positivas tiene 12 ejemplos de entrenamiento, tres de validación y cuatro de prueba. `desconocido` tiene 88, 18 y 24, respectivamente. Esta clase incluye descripciones irrelevantes, peticiones negadas o compuestas, mecánicas no implementadas y tareas que corresponden a otras vías del planificador, como caminar o conducir.

Las intenciones positivas son `bailar`, `saludar`, `aplaudir`, `rendirse`, `mirar_lados`, `rascarse`, `tumbarse`, `vomitar`, `sorpresa`, `conversar`, `estirarse`, `negar_cabeza`, `cansancio`, `miedo`, `celebrar`, `enfado`, `curiosidad`, `fumar`, `reir`, `beber`, `comer` y `telefono`.

Las frases y sus etiquetas base fueron redactadas con asistencia de IA. No son peticiones observadas de usuarios ni anotaciones verificadas por una persona. La separación evita textos duplicados y grupos compartidos entre particiones, pero los 548 grupos actuales son identificadores de ejemplos individuales: no demuestran independencia semántica entre paráfrasis. Las redacciones pueden compartir vocabulario y estilo. La prueba histórica no equivale a una evaluación humana externa. Para estimar la generalización de una futura mejora hará falta otro conjunto de prueba independiente.

## Guardar y revisar correcciones

La aplicación ofrece **Corregir interpretación** y **Revisar correcciones**, tanto junto a la petición como en Configuración:

1. Abre el diálogo, revisa la frase y selecciona el gesto que querías representar. No hay una etiqueta correcta seleccionada por defecto.
2. Pulsa **Guardar para revisión**. La frase, la etiqueta propuesta y la evidencia pública del clasificador se guardan con estado `pendiente`.
3. Selecciona una corrección de la lista de pendientes. El diálogo muestra la frase completa y la etiqueta antes de habilitar la decisión.
4. Pulsa **Aprobar etiqueta** o **Descartar**. Solo las aprobadas podrán entrar en un entrenamiento posterior.

Guardar y revisar **no ejecuta entrenamiento ni modifica el modelo activo**. La aprobación es una acción explícita del usuario; no acredita revisión científica independiente ni validación visual en GTA. Las etiquetas de este corpus base no se convierten automáticamente en anotaciones humanas por disponer de esta herramienta.

El backend [`src/correcciones_intenciones.py`](src/correcciones_intenciones.py) guarda las correcciones en `DATA_ROOT/datos_entrenamiento/correcciones.sqlite3`. Al ejecutar el código fuente, `DATA_ROOT` es la raíz del proyecto; en la aplicación empaquetada es `%LOCALAPPDATA%/MMS-Director/`. Las correcciones permanecen locales y el registro conserva estados `pendiente`, `aprobada` o `rechazada`. Repetir una misma frase con la misma etiqueta conserva su revisión previa.

Al preparar entrenamiento se excluyen correcciones que duplican ejemplos de entrenamiento, contradicen etiquetas ya conocidas o coinciden por texto normalizado o características con validación o prueba. También se controlan duplicados entre correcciones. Las exclusiones quedan registradas con su identificador y motivo en `correcciones_revisadas.omitidas`; los ejemplos base y sus particiones no se modifican.

## Entrenamiento reproducible

Desde la raíz del proyecto fuente:

```powershell
python -m pip install -r requirements-training.txt
python entrenar_intenciones.py
```

La dependencia de entrenamiento utilizada es `scikit-learn==1.9.1`. El procedimiento no consulta APIs de generación. La orden sin opciones entrena con el corpus base y guarda una **versión candidata**, sin reemplazar los pesos activos.

Para incorporar las correcciones aprobadas y utilizables:

```powershell
python entrenar_intenciones.py --usar-correcciones
```

Las correcciones se añaden exclusivamente a entrenamiento. La validación y la prueba histórica siguen siendo las originales. Si no hay correcciones aprobadas nuevas utilizables, la orden termina con una explicación en lugar de afirmar que aprendió de datos nuevos. Cuando todavía no se han aportado y revisado etiquetas nuevas, la mera instalación de este flujo no mejora el modelo activo.

El script [`entrenar_intenciones.py`](entrenar_intenciones.py) realiza los siguientes pasos:

1. Comprueba identificadores, etiquetas, textos duplicados y separación de grupos.
2. Incorpora solo las correcciones aprobadas utilizables cuando se solicita `--usar-correcciones`. Produce tres variantes por ejemplo de entrenamiento: la frase original y dos envolturas de contexto. Sin correcciones, las 352 frases base producen **1056 ejemplos de ajuste**. Estas variantes no son 1056 anotaciones independientes.
3. Normaliza el texto y extrae palabras, pares de palabras y fragmentos de tres, cuatro y cinco caracteres. La extracción es compartida por entrenamiento e inferencia.
4. Ajusta `DictVectorizer` y `TfidfTransformer` usando únicamente esas variantes de entrenamiento. Utiliza TF sublineal y normalización L2.
5. Ajusta regresión logística con pesos de clases equilibrados, semilla 42 y optimizador `lbfgs`. Compara `C=1`, `C=4` y `C=12`.
6. Selecciona `C` y los umbrales exclusivamente con validación, priorizando cobertura bajo las condiciones de precisión y falsos positivos definidas en el script.
7. Exporta los pesos a una carpeta de versión separada y comprueba que la inferencia portable reproduzca las puntuaciones de scikit-learn.
8. Evalúa descriptivamente el modelo en las 112 frases de prueba histórica y guarda el informe, sin utilizar esa prueba para decidir activación.

La primera versión entrenada tiene 5960 características y eligió `C=12`, puntuación mínima `0.60` y margen mínimo de `0.30` entre las dos clases con mayor puntuación. También exige una cobertura mínima de vocabulario de `0.12`. Una candidata con nuevas correcciones puede aprender otro vocabulario o seleccionar otros parámetros. La puntuación softmax no ha sido calibrada con un conjunto probabilístico externo: un valor `0.80` no debe presentarse como una garantía de 80 % de acierto.

## Versiones candidatas y activación

Cada nuevo entrenamiento se guarda en `models/intenciones/versiones/<id_version>/`, con `metadata.json`, `pesos.npz`, `corpus_utilizado.json` e `informe.json`. El snapshot permite consultar exactamente qué ejemplos entraron en esa versión, incluidos los aprobados. Las huellas del corpus base, del entrenamiento y de los pesos permiten identificar su procedencia. `evaluaciones/intenciones_ultimo_entrenamiento.json` describe la última ejecución y su estado.

Para entrenar con correcciones y promover la candidata si supera las condiciones:

```powershell
python entrenar_intenciones.py --usar-correcciones --activar
```

También puedes activar una versión ya entrenada. Sustituye `ID_DE_LA_VERSION` por la carpeta generada:

```powershell
python entrenar_intenciones.py --activar-version "models/intenciones/versiones/ID_DE_LA_VERSION"
```

La activación vuelve a evaluar **solo validación**. Exige al menos tres predicciones aceptadas, precisión entre aceptados de al menos 97 %, cero ejemplos `desconocido` aceptados y, frente al modelo activo, no reducir ni el F1 macro ni la cantidad de aceptaciones correctas. Las métricas de la prueba histórica no intervienen en esta decisión. Si la candidata no cumple, el modelo activo se conserva.

Antes de reemplazar un modelo existente, se guarda su par de archivos en una carpeta `models/intenciones/versiones/respaldo-<fecha>/`. La aplicación carga los pesos activos desde `models/intenciones/`; entrenar sin `--activar` deja ese par intacto. `models/intenciones/activacion.json` registra una promoción realizada. La política sirve para evitar regresiones detectadas en esta validación pequeña, no garantiza mejores resultados con cualquier petición nueva.

Para reevaluar los pesos guardados sin entrenarlos de nuevo:

```powershell
python entrenar_intenciones.py --solo-evaluar
```

Esta orden evalúa el **modelo activo**, no la última candidata, y escribe `evaluaciones/intenciones_reevaluacion.json`. No entrena ni activa versiones. Si el corpus base ha cambiado respecto de la huella del modelo, solicita volver a entrenar.

## Archivos que contienen el aprendizaje

| Archivo | Contenido |
| --- | --- |
| [`models/intenciones/metadata.json`](models/intenciones/metadata.json) | Clases, vocabulario, configuración seleccionada, conteos, versiones y huellas SHA-256 del corpus y de los pesos. |
| [`models/intenciones/pesos.npz`](models/intenciones/pesos.npz) | Arrays `idf`, `coef` e `intercept`, aprendidos durante el ajuste. |
| [`evaluaciones/intenciones_supervisadas.json`](evaluaciones/intenciones_supervisadas.json) | Métricas, matriz de confusión, resultados por frase y selección realizada con validación. |
| `models/intenciones/versiones/<id_version>/` | Cada candidata conserva sus pesos, metadatos, corpus utilizado e informe; también contiene los respaldos de promociones anteriores. |
| `evaluaciones/intenciones_ultimo_entrenamiento.json` | Último entrenamiento ejecutado, correcciones incorporadas o excluidas y estado candidata/activa. |

La aplicación ejecuta [`src/modelo_intenciones.py`](src/modelo_intenciones.py) con NumPy y la biblioteca estándar. Reconstruye TF-IDF, calcula los logits y aplica softmax. No necesita cargar scikit-learn, ejecutar `pickle` ni consultar un servicio remoto para inferir. Verifica la huella y las dimensiones de los arrays exportados antes de utilizarlos.

El archivo antiguo `modelo_clasificador_gta.pkl` no participa en esta implementación; se conserva intacto.

## Cómo influye en una escena real

El recorrido de una petición simple es:

```text
Texto del usuario
  → reglas locales existentes o clasificador supervisado para expresiones nuevas
  → intención aceptada
  → correspondencia explícita con un clip real del catálogo
  → plan validado y propuesta editable
  → compilador de Mission Maker
  → archivo .mms
```

En [`src/capacidades_escena.py`](src/capacidades_escena.py), `candidata_local` conserva las reglas existentes y consulta `candidata_aprendida` cuando esas reglas no reconocen la expresión. La intención aprendida se vincula después a una familia y a un clip real. **La correspondencia de intención a clip está programada; el modelo aprende la relación entre el texto y la intención.** No aprende físicamente a animar un personaje ni crea clips nuevos.

[`src/busqueda_animaciones.py`](src/busqueda_animaciones.py) también incorpora candidatos procedentes del clasificador y adjunta su evidencia. [`src/mvp_plan.py`](src/mvp_plan.py) identifica las propuestas aceptadas por aprendizaje supervisado y permite resolverlas localmente antes de esperar o consultar una API. El plan registra el campo `aprendizaje_supervisado`, con intención, puntuación, margen, identificador de modelo y huella de pesos. La exportación conserva el plan como evidencia de la decisión utilizada.

Ejemplos para comprobar la función desde la aplicación:

- `una persona se mueve al ritmo de la musica`
- `una persona junta las palmas repetidamente`
- `una persona atiende una llamada`

Estas expresiones sirven para demostrar que los pesos entrenados intervienen en reconocer baile, aplausos o teléfono cuando la regla original no reconoce esas palabras. La selección sigue limitada a recursos y mecanismos que el compilador ya puede representar.

## Abstención y límites

El modelo se limita a un gesto por petición. Las guardas de alcance evitan usarlo automáticamente ante negaciones, relaciones o acciones compuestas y ciertas mecánicas ajenas a este clasificador. También se abstiene ante incertidumbre, poco vocabulario conocido, clase `desconocido` o ausencia de pesos compatibles.

Estas guardas son reglas de protección del planificador; **no son conocimiento aprendido**. Cuando el clasificador se abstiene, la aplicación mantiene disponibles las vías habituales de reglas y proveedores de IA. Esto no equivale a declarar que la petición sea imposible en todo el proyecto.

La aprobación del clasificador no acredita que el gesto resulte visualmente correcto en GTA. Por ejemplo, una animación de fumar no crea por sí sola un cigarrillo o humo. Las restricciones de participantes, duración, recursos, rutas y compilación siguen aplicándose. El entrenamiento no amplía por sí mismo las mecánicas del mod.

## Resultados históricos medidos

Estos resultados proceden de la primera versión, entrenada y evaluada sobre el corpus base de 548 frases. Son mediciones reales que se conservan como referencia histórica. Añadir la revisión y el versionado no los convierte en resultados de una versión mejorada; si no se han revisado etiquetas nuevas ni promovido otra versión, el modelo activo conserva su aprendizaje anterior:

| Métrica | Resultado | Interpretación |
| --- | ---: | --- |
| Exactitud de clasificación | 87,50 % | 98 de 112 etiquetas predichas correctamente, antes de la política de aceptación. |
| F1 macro | 0,8762 | Promedio del F1 de las 23 clases, dando el mismo peso a cada clase. |
| Precisión entre aceptados | 94,83 % | 55 decisiones correctas entre 58 aceptadas por la política completa. |
| Cobertura correcta de positivos | 62,50 % | 55 de los 88 ejemplos positivos fueron aceptados con la intención correcta. |
| Desconocidos aceptados erróneamente | 1 de 24 | Tasa de falsos positivos de 4,17 % en los negativos de prueba. |

La exactitud y el F1 describen el clasificador. Las métricas de aceptación incorporan umbral, margen, cobertura de vocabulario y guardas. La precisión entre aceptados no significa que se resuelva correctamente el 94,83 % de todas las peticiones: el sistema se abstiene en parte de ellas. Tampoco equivale a la tasa de reproducción correcta de MMS en GTA.

El informe conserva los errores y los resultados por clase. Con solo cuatro ejemplos positivos por clase en prueba, las métricas por intención tienen mucha incertidumbre. La validación usada para elegir umbrales y la prueba pueden rendir distinto; los umbrales no se reajustan usando los errores de prueba de este informe.

El evaluador `evaluar_intenciones.py` registra la integración y la ablación en `evaluaciones/integracion_modelo_intenciones.json`: compara la interpretación con y sin modelo y comprueba la compilación real a MMS. Estos resultados deben consultarse en su propio informe; no se deducen de las métricas anteriores. La compilación comprobada sigue sin sustituir la ejecución visual dentro del juego.

```powershell
python evaluar_intenciones.py
python evaluar_intenciones.py --exportar-ejemplos
```

La evaluación ejecutada sobre los **88 gestos positivos reservados** produjo:

| Configuración | Peticiones con clip correcto y MMS compilado |
| --- | ---: |
| Reglas anteriores, modelo deshabilitado | 31 de 88 (35,23 %) |
| Reglas y modelo entrenado | 58 de 88 (65,91 %) |

Se resolvieron **27 peticiones adicionales gracias al modelo**, sin regresiones en estos 112 casos.
Las 24 frases ajenas al clasificador tuvieron una falsa aceptación de gesto en ambas configuraciones.
Esto mide la aportación en este corpus específico y no constituye un benchmark contra Gemini u otros modelos.
La ejecución con exportación produjo tres MMS y sus JSON con procedencia, entre ellos
[«el protagonista marca pasos al compás de la música»](salida_mms/caminata_20261110_195152_db31b3.mms)
y su [plan con la huella del modelo](salida_mms/caminata_20261110_195152_db31b3.json).
La opción de exportación añade hasta tres ejemplos nuevos a `salida_mms/` y registra
sus rutas en esa ejecución del informe; no modifica pesos. Reevaluar sin esa opción
no vuelve a exportar y deja vacía la lista de exportaciones de la nueva ejecución.

La verificación posterior pasó **126 pruebas automatizadas** y los **1305 casos locales**
de `python evaluar_escenas.py`. Estos últimos comprueban que se conserva la cobertura
anterior; no son nuevos ejemplos usados para entrenar el clasificador. Ese conteo de
126 corresponde a la primera integración; las pruebas del flujo posterior de
correcciones y versiones se reportan en su ejecución actual.

## Comparación real de seis clasificadores

El experimento [`COMPARACION_MODELOS.md`](COMPARACION_MODELOS.md) compara regresión logística, SVM lineal, Naive Bayes multinomial, Naive Bayes complementario, Ridge y SGD logístico. Sus [resultados JSON](evaluaciones/comparacion_clasificadores.json) y [CSV](evaluaciones/comparacion_clasificadores.csv) proceden de ajustes ejecutados sobre las mismas particiones y representación textual. Son seis clasificadores supervisados locales; el experimento no compara seis proveedores LLM ni mide calidad visual en GTA.

El benchmark no cambia ni selecciona automáticamente el modelo activo. La curva de aprendizaje compara distintos tamaños de entrenamiento únicamente sobre validación. La prueba histórica se muestra de forma descriptiva, con parámetros prefijados, y no sustituye una nueva evaluación independiente.

```powershell
python -m pip install -r requirements-analysis.txt
python comparar_clasificadores.py
```

La comparación puede ejecutarse con `--sin-graficas` cuando solo se necesitan JSON y CSV. `--solo-graficas` permite representar un informe ya calculado sin repetir los ajustes. Los formatos y rutas finales de las figuras se describen en el documento de comparación.

## Distribución y presentación

La preparación de recursos copia `models/intenciones/metadata.json` y `pesos.npz` al paquete. Es necesario volver a compilar para que el ejecutable existente incorpore el código y estos recursos; modificar el proyecto fuente no actualiza automáticamente el `.exe`. Este documento no afirma que el ejecutable haya sido reconstruido.

Una descripción adecuada para las diapositivas es:

> Entrenamos un clasificador supervisado de intenciones en español con TF-IDF y regresión logística multiclase. Aprendió sus parámetros con 352 frases base de entrenamiento y variantes de contexto; seleccionamos configuración con 84 frases y evaluamos con 112 frases reservadas. Sus predicciones permiten reconocer expresiones nuevas de 22 gestos, seleccionar clips existentes y generar planes compilables a Mission Maker. El sistema conserva reglas y otros modelos para las peticiones fuera de ese alcance.

Al presentar sus métricas, debe indicarse que el corpus es pequeño, artificial y redactado con asistencia de IA, que existe abstención y que falta validación independiente con usuarios y reproducción visual de las escenas.
