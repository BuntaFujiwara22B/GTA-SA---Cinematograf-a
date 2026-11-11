# Convertir las capturas en contexto para la aplicacion

## Dejarlo trabajando durante la noche

Cierra cualquier analizador previo con Ctrl+C. En una terminal del proyecto ejecuta:

```powershell
python -u analizar_noche.py --horas 12
```

Descubre todos los modelos publicados de OpenRouter con sufijo `:free`, entrada de imagen, salida de texto y precio cero; agrega los tres Gemini configurados. La lista de cada ciclo queda en `assets/animations/catalogo_completo/modelos_noche.json`. Se verifica otra vez el precio antes de usar cada modelo. No compra credito, cambia claves ni aumenta limites.

Guarda una descripcion valida por animacion y no repite las guardadas. Si recibe respuestas invalidas, falta de permisos o limites, intenta otro modelo. Cuando se agotan las alternativas, espera 60 minutos y vuelve a intentar las pendientes. El plazo de 12 horas limita el inicio de nuevos ciclos; un ciclo en curso puede extenderse. Ctrl+C detiene y permite reanudar. Un bloqueo de archivo impide que dos analizadores escriban simultaneamente.

Deja el PC encendido, conectado a Internet y sin suspension. No hace falta mantener abierto GTA. Las cuotas compartidas de OpenRouter no se multiplican por la cantidad de modelos; el modo nocturno no garantiza terminar en una noche. Gemini solo sigue siendo gratuito si el proyecto Google esta en Free Tier; el script no puede imponerlo. Mantener la clave OpenRouter con limite de gasto cero.

Las respuestas de distintos modelos pasan el mismo validador, pero la validez del JSON no garantiza exactitud visual. Las descripciones dudosas siguen requiriendo revision.

Se organizaron 7578 PNG de la tanda `animaciones_catalogo_20261108_125117.csv` en 1263 animaciones. Los originales siguen en `Pictures/Screenshots/animaciones_total`; las copias y `catalogo.json` estan en `assets/animations/catalogo_completo`. El emparejado se basa en orden numerico y presupone que no hubo capturas ajenas intercaladas.

## Analizar

Desde la terminal del proyecto:

```powershell
# Comprueba archivos y pendientes SIN enviar nada:
python analizar_animaciones.py

# Primera prueba: envia seis PNG por cada una de 10 animaciones:
python analizar_animaciones.py --ejecutar --limite 10

# Tras revisar las descripciones, procesa todas las pendientes:
python analizar_animaciones.py --ejecutar --limite 0
```

Utiliza `GEMINI_API_KEY` del `.env` existente. El modelo predeterminado es `gemini-3.5-flash`, el utilizado en esta aplicacion; se puede cambiar con `--modelo NOMBRE`. La disponibilidad y cuotas dependen de la cuenta. El script no puede garantizar gratuidad: si el proyecto tiene facturacion habilitada, las solicitudes pueden generar cargos. Las imagenes se envian a Google al usar `--ejecutar`.

Se guardan los resultados tras cada animacion en `descripciones.json`. Repetir el comando omite las ya analizadas. Si aparece 429 u otro error de disponibilidad o autenticacion, se detiene y conserva el avance; resolverlo antes de repetir. Ctrl+C tambien permite continuar posteriormente, aunque puede repetir la ultima solicitud si fue interrumpida antes del guardado.

### Varios modelos Gemini

`--modelos` acepta nombres exactos separados por espacios, en orden de preferencia. Usa solo modelos con vision, salida JSON y cuota gratuita confirmada en tu proyecto. No hay deteccion automatica de facturacion: aparecer en la lista de modelos no garantiza acceso gratuito.

Ante 429 o 404 se retira ese modelo durante la ejecucion y se intenta la misma animacion con el siguiente. Los errores temporales 500/503/504 tienen dos reintentos antes de pasar al siguiente. Cuando todos quedan fuera, se guarda el avance y se detiene. Reiniciar el comando vuelve a intentar los modelos configurados y omite descripciones ya guardadas. No crea cuentas ni cambia de clave para eludir limites. Esta opcion solo admite modelos Gemini con la clave existente; otros proveedores necesitan una integracion distinta. Las cuotas son por proyecto y modelo, por lo que un cambio puede no aportar cuota adicional. Cada resultado conserva el nombre del modelo que lo genero.

No usa el chat de Gemini ni entrena sus pesos. La API recibe una secuencia por solicitud con categoria y nombre tecnico como pistas. Decide cuales frames no sirven, describe al NPC y separa observacion de interpretacion. Se conservan los descartados; no se asume que todas las fotos pequenas sean azules. Si la evidencia no basta, marca revision. Puede haber respuestas bloqueadas: quedan pendientes, sin descripciones inventadas.

## Usar en la app

### Groq

Si existe `GROQ_API_KEY` en `.env`, `analizar_noche.py` agrega automaticamente `groq:qwen/qwen3.8-27b` en cada nuevo proceso. Si el proceso ya estaba abierto al cambiar el codigo, detener con Ctrl+C y reiniciar para cargar el adaptador nuevo.

Groq admite tres imagenes por solicitud para este modelo. Se construyen en memoria tres laminas JPEG con dos poses completas cada una, numeradas FRAME 1 a FRAME 6, sin recortar ni modificar los PNG originales. Se comprueba la misma estructura de descripcion que en los otros proveedores. La reduccion de tamano puede dificultar movimientos pequenos.

```powershell
# Prueba separada, no interfiere con un analizador activo:
python probar_groq.py

# Analisis solo con Groq (requiere que no haya otro analizador escribiendo):
python analizar_animaciones.py --ejecutar --limite 10 --modelos groq:qwen/qwen3.8-27b
```

La prueba separada se guarda en `assets/animations/catalogo_completo/prueba_groq.json`, no se mezcla automaticamente con el catalogo para evitar competir con un proceso activo. Groq informa tokens pero no certifica costo en esa respuesta. Mantener el plan gratuito de Groq; el adaptador no puede verificar el estado de facturacion de la cuenta. Documentacion: https://console.groq.com/docs/vision y https://console.groq.com/docs/rate-limits

### Respaldo con OpenRouter

Guardar `OPENROUTER_API_KEY` en `.env`, sin compartirla en el chat. El adaptador solo acepta modelos con sufijo `:free`, comprueba precio cero y entrada de imagenes en `/models` y limita el precio de enrutamiento a cero.

Prueba de una animacion solo en OpenRouter:

```powershell
python analizar_animaciones.py --ejecutar --limite 1 --modelos openrouter:nvidia/nemotron-3.5-super-vl:free
```

Cadena con Gemini y dos modelos gratuitos de OpenRouter:

```powershell
python analizar_animaciones.py --ejecutar --limite 0 --modelos gemini-3.5-flash gemini-3.7-flash gemini-3.1-flash-lite openrouter:nvidia/nemotron-3.5-super-vl:free openrouter:dots-studio/dots-3-note-preview:free
```

OpenRouter usa su propia cuota: no se reinicia por cambiar de modelo. Un 401 indica rechazo de autenticacion; un 402 puede indicar un bloqueo de credito. No aumentar el limite de gasto como primera solucion. Conservar el limite $0 y revisar la clave si la autenticacion falla. El costo informado por el proveedor se imprime al recibir una respuesta; no es una estimacion. La opcion Gemini sigue dependiendo del nivel de facturacion del proyecto de Google.

`src/ia_client.py` lee `src/todo.txt` y proporciona todas las opciones de animacion inmediatamente, aunque no haya descripciones visuales. `src/catalogo_animaciones.py` valida categorias e indices y construye identificadores completos. Incorpora tambien las descripciones existentes con sus marcas de confianza y revision; se priorizan las claras, pero no se ocultan las otras opciones. Un nombre tecnico permite sugerir una candidata, no confirmar su movimiento. Las sugerencias con identificadores inexistentes se descartan. Esto no entrena los pesos del modelo ni garantiza que todos los nombres describan correctamente el movimiento. Las nuevas consultas incorporan automaticamente las descripciones que termine de generar el analizador.

La aplicacion consulta las descripciones guardadas; no reenvia las 7578 fotos con cada peticion. El analisis original ya relaciona cada descripcion con sus fotos y con categoria, indice, biblioteca y nombre. La seleccion no ejecuta por si sola una animacion dentro del juego: el generador de misiones debe convertir ese identificador al formato real de Mission Maker.

Esta integracion incluye todo.txt y este catalogo visual. Otros documentos de contexto, catalogos de objetos y vehiculos o esta conversacion no se agregan automaticamente; requieren fuentes seleccionadas y una integracion explicita. Para entrenamiento real harian falta un modelo compatible, datos etiquetados y revisados y un conjunto de evaluacion separado. No hace falta para consultar el catalogo.

Documentacion oficial: https://ai.google.dev/gemini-api/docs/image-understanding y https://ai.google.dev/gemini-api/docs/pricing
