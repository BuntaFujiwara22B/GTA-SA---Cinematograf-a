# Comparación real de clasificadores supervisados

`comparar_clasificadores.py` entrena y mide seis clasificadores de intención textual
sobre el corpus base congelado. No usa APIs ni altera el modelo activo. Los modelos
comparados son regresión logística, SVM lineal, Naive Bayes multinomial, Naive Bayes
complementario, Ridge y SGD logístico.

Esta comparación corresponde a **seis clasificadores supervisados locales**. No es
una comparación de seis LLM como Gemini o Qwen. Tampoco mide ejecución visual de MMS.

## Ejecutar

```powershell
python -m pip install -r requirements-analysis.txt
python comparar_clasificadores.py
```

Sin la dependencia de gráficos:

```powershell
python comparar_clasificadores.py --sin-graficas
```

Para dibujar un informe existente sin repetir entrenamientos:

```powershell
python comparar_clasificadores.py --solo-graficas
```

Se generan `evaluaciones/comparacion_clasificadores.json` y su CSV. Cuando matplotlib
está disponible también se guardan gráficos de calidad, latencia y curva de aprendizaje
en `evaluaciones/graficas/`, en formatos PNG, SVG y PDF para usar en diapositivas.

Figuras generadas a partir del informe medido:

- [Comparación de calidad](evaluaciones/graficas/calidad_clasificadores.png).
- [Latencia de los seis clasificadores](evaluaciones/graficas/latencia_clasificadores.png).
- [Curva de aprendizaje](evaluaciones/graficas/curva_aprendizaje_intenciones.png).

En esta sesión se preparó el entorno local `.venv-analysis`, con acceso a los paquetes
existentes y Matplotlib instalado dentro del proyecto. Para regenerar estas figuras
sin entrenar otra vez:

```powershell
.\.venv-analysis\Scripts\python.exe comparar_clasificadores.py --solo-graficas
```

## Resultados ejecutados sobre el corpus base

| Clasificador | F1 macro en validación | Exactitud en prueba histórica | F1 macro en prueba histórica |
| --- | ---: | ---: | ---: |
| Regresión logística | 0,8880 | 87,50 % | 0,8762 |
| SVM lineal | 0,9002 | 86,61 % | 0,8704 |
| Naive Bayes multinomial | 0,6651 | 73,21 % | 0,7534 |
| Naive Bayes complementario | 0,8619 | 83,04 % | 0,8366 |
| Ridge | 0,8615 | 83,04 % | 0,8535 |
| SGD logístico | 0,8743 | 87,50 % | 0,8762 |

Los seis ajustes terminaron sin advertencias de convergencia. Se verificó que las
huellas del modelo activo fueran iguales antes y después del experimento. La SVM
obtuvo el mayor F1 en validación, mientras que regresión logística y SGD empataron
en esta prueba histórica. Ese orden no determina automáticamente un cambio en la
aplicación: la abstención y su integración requieren otra evaluación específica.

La curva de aprendizaje de regresión logística produjo los siguientes valores:

| Frases base de entrenamiento | F1 macro medio en validación | Desviación entre tres semillas |
| --- | ---: | ---: |
| 88 | 0,5854 | 0,0533 |
| 176 | 0,7435 | 0,0042 |
| 264 | 0,8318 | 0,0108 |
| 352 | 0,8880 | 0,0000 |

En este experimento, disponer de más frases base mejoró el F1 de validación. No
permite extrapolar que esa mejora continúe indefinidamente ni garantiza un valor
para un corpus futuro. Con el 100 % de los grupos, las tres semillas incluyen los
mismos ejemplos y el ajuste determinista da desviación cero.

## Método

- Corpus artificial asistido: 352 frases de entrenamiento, 84 de validación y 112 de
  prueba histórica. Las 352 bases de entrenamiento producen 1056 variantes; estas
  variantes no son anotaciones independientes.
- Misma extracción de palabras, bigramas y fragmentos de caracteres; vocabulario e
  IDF ajustados exclusivamente con entrenamiento. La representación TF-IDF es la
  misma para los seis algoritmos.
- Parámetros prefijados: regresión logística `C=12`, SVM lineal `C=1`, ambos Naive
  Bayes `alpha=1`, Ridge `alpha=1`, SGD con pérdida logística y `alpha=0.0001`.
  Se usa ponderación equilibrada de clases cuando corresponde, semilla 42 y un hilo
  BLAS. No se hace una búsqueda exhaustiva por algoritmo.
- Primero se entrenan y evalúan todos los candidatos con validación. Después se
  evalúa la prueba histórica con las configuraciones ya congeladas. Sus resultados
  son descriptivos: no seleccionan ni activan un reemplazo para la aplicación.
- Se registran exactitud, F1 macro, matriz de confusión, métricas por clase, tiempo
  de ajuste y latencia. La latencia incluye texto → características → TF-IDF →
  predicción, con una petición por lote, tres calentamientos y treinta mediciones.
  No incluye carga inicial, interfaz, red ni GTA.
- La curva usa regresión logística y fracciones 25 %, 50 %, 75 % y 100 % de los
  grupos base de entrenamiento. Se muestrean grupos estratificados antes del aumento,
  con tres semillas. La evaluación de esa curva utiliza únicamente validación.
- Se guardan las huellas SHA-256 del corpus y del modelo activo antes y después.
  Si el modelo activo cambia durante la ejecución, el benchmark se detiene para
  evitar atribuirle resultados de otro estado del proyecto.

## Interpretar los resultados

Los valores del JSON, CSV y figuras proceden de entrenamientos ejecutados. Un F1
mayor en este corpus no demuestra mejor comportamiento universal. La prueba de 112
frases ya fue utilizada para evaluar la primera versión; no constituye una evaluación
externa nueva. Las particiones comparten dominio y estilo y tienen pocos ejemplos
por clase. Para evaluar una futura versión mejorada se necesita otro conjunto de
prueba independiente, preferiblemente escrito y revisado por personas.

Aquí se mide la clase predicha antes de la abstención y de las reglas del planificador.
Por eso no se debe comparar directamente su exactitud con la precisión de las
predicciones aceptadas del modelo desplegado ni con su tasa de compilación MMS.

Los tiempos dependen del equipo, de los procesos concurrentes y de las versiones de
las bibliotecas. Se mide un ajuste por algoritmo; la curva sí repite tres semillas.
Los informes conservan advertencias de convergencia si un algoritmo las produce.

La frase adecuada para una diapositiva es:

> Entrenamos seis clasificadores supervisados con la misma representación textual
> y las mismas particiones. Medimos su calidad y tiempo localmente y mantuvimos
> separado el experimento de la elección del modelo activo. Los resultados proceden
> de un corpus artificial pequeño y no de una evaluación visual en GTA.
