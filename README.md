# MMS-Director

Aplicación de escritorio para preparar escenas de GTA San Andreas y exportarlas en formato `.mms` de Mission Maker.

Al analizar una petición se prepara una propuesta de personajes, vehículo si corresponde, ubicación y ambiente. Gemini puede decidir esas opciones entre los catálogos disponibles; si la API no responde, se usa un respaldo local identificado como tal. El flujo abre directamente la elección de cámara y después permite elegir música o continuar sin ella. Los botones de la propuesta permiten modificar cualquier elección antes de generar.

## Ejecutar

En el proyecto original:

```powershell
python main.py
```

El paquete para Windows está en `dist/MMS-Director/`. Abre `MMS-Director.exe` y conserva a su lado la carpeta `_internal`. Para llevarlo a otro PC debes copiar **toda** la carpeta `MMS-Director`; copiar únicamente el ejecutable no basta. El paquete incluye Python, el cliente Flet y los pesos locales de CLIP. No incluye GTA ni las claves API del autor.

En **Configuración**, introduce tu clave Gemini, el modelo disponible en tu cuenta y la carpeta que contiene `gta.exe`. El comprobador de rutas requiere MoonLoader en esa instalación de GTA. El botón para instalarlo conserva una copia del comprobador anterior.

La versión empaquetada guarda configuración, clave, exportaciones y música en `%LOCALAPPDATA%/MMS-Director/`. La música propia se coloca en `music/mistica/` o `music/feliz/` dentro de esa carpeta. Al ejecutar desde el código fuente se mantienen `.env`, `salida_mms/` y `assets/music/` del proyecto.

## Gemini y CLIP

El proyecto también incluye un **clasificador supervisado entrenado de intenciones**:
aprende de frases etiquetadas y permite convertir nuevas paráfrasis de 22 gestos en
animaciones reales del catálogo, sin llamar a una API cuando la predicción supera
los criterios de aceptación. Las reglas y validadores siguen comprobando el plan.
Los pesos activos están en `models/intenciones/`. **Corregir interpretación** permite
guardar una frase con su etiqueta; **Revisar correcciones** permite aprobarla o
descartarla después de leerla. Estos controles están junto a la petición y en
Configuración. Guardar o aprobar conserva los pesos actuales.

Desde el código fuente, con `requirements-training.txt` instalado:

```powershell
python entrenar_intenciones.py --usar-correcciones
```

Esta orden incorpora solo correcciones aprobadas y utilizables y guarda una versión
candidata en `models/intenciones/versiones/`. Para entrenar e intentar activarla:

```powershell
python entrenar_intenciones.py --usar-correcciones --activar
```

La activación evalúa validación: exige precisión entre aceptados de al menos 97 %,
cero desconocidos aceptados y que no empeoren F1 ni cantidad de aceptaciones
correctas frente al modelo activo. Conserva un respaldo antes de reemplazarlo.
`python entrenar_intenciones.py` también guarda una candidata, usando solo el corpus
base; **entrenar sin `--activar` no cambia el modelo utilizado por la aplicación**.
Si no hay correcciones aprobadas nuevas, `--usar-correcciones` lo indica sin entrenar.

Las correcciones se guardan en `datos_entrenamiento/correcciones.sqlite3` dentro de
la carpeta de datos del usuario: el proyecto al ejecutar el código fuente y
`%LOCALAPPDATA%/MMS-Director/` en el ejecutable. El corpus, la revisión, el versionado,
las métricas históricas y la comparación con/sin modelo se explican en
[ENTRENAMIENTO_IA.md](ENTRENAMIENTO_IA.md).

También hay una [comparación real de seis clasificadores locales](COMPARACION_MODELOS.md),
con [resultados JSON](evaluaciones/comparacion_clasificadores.json) y
[CSV](evaluaciones/comparacion_clasificadores.csv). Mide clasificación de texto;
la comparación de proveedores LLM y la reproducción de escenas en GTA requieren
experimentos diferentes. El benchmark mantiene el modelo activo sin cambios.

Gemini interpreta la petición con el contexto del mod y los catálogos existentes. Se mantienen la caché de respuestas, el control de peticiones simultáneas y el tratamiento de límites de cuota. El modelo se puede configurar sin editar código. Una clave válida no garantiza cuota disponible.

CLIP busca fotografías de clima próximas a expresiones como lluvia o atardecer en un índice local de 1073 fotos. Aporta referencias al análisis; no cambia el identificador de clima seleccionado por el usuario ni entrena Gemini. Se carga cuando hace falta y consulta pesos ya descargados.

Para comprobar la conexión desde el proyecto sin mostrar la clave:

```powershell
python diagnostico_api.py
python diagnostico_api.py --generar
```

La segunda orden consume una petición breve a Gemini.

## Compilar de nuevo

Entorno usado: Windows x64 y Python 3.12. Instala `requirements.txt` y, para la versión con CLIP, `requirements-vision.txt`. El cliente de escritorio Flet y los pesos CLIP deben estar disponibles localmente antes de preparar recursos.

```powershell
powershell -ExecutionPolicy Bypass -File compilar.ps1
```

La opción `-Ligero` permite compilar sin el motor CLIP. El script no incluye `.env`, capturas de investigación ni música personal. El instalador está definido en `installer/MMS-Director.iss`; se compila si `ISCC.exe` de Inno Setup está disponible en el PATH. El ejecutable portable no necesita ese compilador.

## Verificar

```powershell
python -m unittest discover -s tests -q
python evaluar_peticiones.py
python medir_rendimiento.py
```

El ejecutable admite `--self-check RUTA_JSON` y `--clip-check RUTA_JSON` para comprobar sus recursos sin abrir ventanas. Al lanzarlo desde PowerShell conviene esperar al proceso para leer el informe.

Las pruebas revisan planificación, estructura MMS, interfaz simulada y portabilidad. No sustituyen la reproducción en GTA ni una medición de FPS en el equipo de destino.

Detalles de esta revisión: [OPTIMIZACION.md](OPTIMIZACION.md).

Las nuevas opciones de lugares aleatorios, entrada y conducción, cámara frontal, velocidad y paquetes con música se explican en [CONDUCCION_Y_ESCENAS.md](CONDUCCION_Y_ESCENAS.md).
