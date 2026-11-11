# Revisión de rendimiento y distribución

Se conservan los flujos de creación y las fotografías originales de los catálogos.

## Cambios

- Lectura JSON compartida con caché que se invalida al cambiar el archivo.
- Actualizaciones de controles concretos para el carrusel, mapa y ambiente, evitando reconstruir toda la página en esas interacciones.
- Animaciones de las letras interpoladas por el cliente Flutter.
- Carga diferida de CLIP y eliminación de la carga inicial de un clasificador que la interfaz no utilizaba. El archivo del clasificador se conserva.
- 1463 vistas ligeras WebP: aproximadamente 1361 MB de imágenes usadas como fuente pasan a 120 MB de vistas para la interfaz. Los originales siguen disponibles.
- 66 vehículos revisados: 63 recortes transparentes activados; combine (532), rhino (432) y swatvan (601) mantienen la fotografía original por defectos del recorte.
- Eliminados 123 duplicados exactos de carpetas antiguas, conservando una copia idéntica por SHA-256 y los archivos únicos. Liberados aproximadamente 111 MiB. Registro: `evaluaciones/limpieza.json`.
- Rutas de recursos separadas de los datos editables del usuario, configuración en la interfaz y empaquetado de escritorio sin claves personales.

## Evidencia y límites

Gemini completó una petición de diagnóstico real con el modelo configurado. CLIP generó un índice local de 1073 imágenes y recuperó candidatos para lluvia y atardecer.

El ejecutable compilado pasó `--self-check` y `--clip-check` desde un directorio distinto al del programa. Encontró 1263 animaciones, 264 actores, 66 vehículos y 57 objetos; CLIP recuperó dos fotografías de atardecer usando los pesos incluidos. No se encontró `.env` dentro de los recursos distribuidos. Informes: `evaluaciones/ejecutable.json` y `evaluaciones/clip_ejecutable.json`.

Las 53 pruebas automatizadas pasaron. Los tiempos de CPU registrados en `evaluaciones/rendimiento.json` muestran una mediana de lectura JSON de 1,440 ms sin caché y 0,144 ms con caché; consulta de foto 0,682 ms y semáforos 0,382 ms. Son micropruebas, no tiempos de renderizado.

Además, 2501 de 2501 peticiones de regresión pasaron la interpretación local y la estructura exportada (`evaluaciones/resultado_peticiones.json`). Este resultado no mide las respuestas de Gemini ni la calidad visual en GTA.

No se ha demostrado una frecuencia constante de 60 FPS. Falta medir el renderizado y probar el paquete en otro PC con su propia instalación de GTA. La estructura del archivo MMS y su reproducción en el juego son verificaciones diferentes.

El paquete portable usa varios archivos para evitar descomprimir todos los recursos en cada arranque. El instalador de Inno Setup está preparado como script; su compilación requiere ese compilador externo.
