El corpus nuevo está en `evaluaciones/escenas_lenguaje_natural.json`: 1305 peticiones naturales,
1297 escenas esperadas y 8 controles negativos. Incluye la ampliación de gestos y 73 casos de techo de vehículo;
varía también reparto, roles, lugares, clima, duración y vehículos. No incluye los 1263 nombres
de clips como si fueran 1263 peticiones naturales diferentes.

Para usar la aplicación actualizada, reinicia `python main.py`. El ejecutable empaquetado anterior
no incluye estos cambios. Escribir actualiza las comprobaciones locales; pulsar **Analizar**
solicita el plan a la IA. Se conserva la caché y una sola consulta simultánea. Un error o una cuota
agotada de un proveedor no bloquea automáticamente al otro.

El plan contiene tareas estructuradas; el programa las valida y compila a `.mms`. Gemini recibe
el catálogo completo de animaciones, las descripciones existentes, todo.txt, referencias MMS,
mapa y referencias visuales candidatas. Groq recibe un contexto recuperado más corto porque
enviar el contexto completo excedía su límite. Las claves no forman parte de los informes.

Se incorporan secuencias de hasta ocho tareas (saltar, clips, caminar/correr/nadar/escaleras y
apuntar a otro actor), selección por roles documentados en los 264 personajes disponibles y
un vehículo sin conductor visible. Para este último el mod crea un conductor técnico invisible.
La conducción existente conserva su espera de entrada y su archivo externo CARREC.

Los clips se eligen por ID real y se programan por objetivos sucesivos. Por ejemplo, salto en
OBJ=0, baile en OBJ=1 y carrera en OBJ=2. El salto tiene un tiempo reservado orientativo de
dos segundos; no se ha medido la duración de cada tarea en el juego. Los recorridos que no
caben en el tiempo se rechazan, y las sugerencias automáticas se acortan antes de exportar.

El catálogo de roles procede del `data/peds.ide` del GTA instalado y se contrastaron las capturas
de uniformes y skins rurales. Un rol criminal es una categoría narrativa/del juego, no una
conclusión sobre una persona por su apariencia. Se puede repetir una skin rural para tener
tres o cuatro actores del mismo oficio sin completar el reparto con civiles genéricos.

El puente está asociado a la posición del MMS y las capturas aportadas por el usuario. Su
segmento de ruta es una propuesta y necesita comprobar colisiones y trenes en GTA. Las
otras ubicaciones siguen usando los nodos y alturas del catálogo existente. Ver el mapa no
garantiza una ruta sin obstáculos. Para agua y escaleras sigue siendo necesario indicar un
recorrido adecuado. No se afirma haber identificado visualmente todos los lugares del mapa.

Para repetir la evaluación local completa:

```powershell
python evaluar_escenas.py
```

Comprueba aceptación, orden de acciones, roles, lugar etiquetado, participantes, arma/blanco,
duración y estructura MMS. Genera los MMS en memoria y guarda el informe en
`evaluaciones/resultado_escenas_local.json`. No consume API ni guarda miles de misiones.
Los cinco ejemplos iniciales también tienen pruebas de petición → interfaz → archivo.

Para evaluar respuestas reales, con pausas y guardado tras cada petición:

```powershell
python evaluar_escenas.py --proveedor ia --limite 10
python evaluar_escenas.py --proveedor gemini --limite 10
```

`ia` permite Gemini o el respaldo Groq y registra cuál respondió en cada caso. `gemini` solo
cuenta respuestas de Gemini. Ninguna opción cuenta un plan local como respuesta de un modelo.
Repetir el comando continúa los pendientes; `--reintentar-fallos` vuelve a intentar los casos
fallidos conservando su intento anterior. Si no responde el proveedor, se detiene y guarda el
diagnóstico. Se puede quitar `--limite` para continuar el corpus hasta terminar o agotar cuota.
No se han enviado 1305 consultas a las APIs.

`python evaluar_escenas.py --proveedor ia --revalidar` comprueba de nuevo los planes reales
ya guardados con el validador actual, sin API. El informe marca esta reutilización y conserva
el resultado anterior. El baile, los aplausos y la sorpresa admiten clips alternativos
contrastados: no se exige el mismo clip concreto cuando expresa la misma acción.

Estos informes evalúan el sistema completo (modelo + validación + compilación), no la salida
cruda de un modelo. Tampoco prueban reproducción visual en GTA. La prueba final debe
comprobar en el juego posición, obstáculos, ejecución, encuadre y sincronización. Las acciones
simultáneas distintas, combate y combinaciones con conducción ajenas al anclaje de techo aún requieren ampliar
el compilador; el corpus no significa que toda petición imaginable esté implementada.

Las tareas nativas nuevas se contrastaron con Mission Maker 1.87, archivo original
`Source/Mission/Loader/EntityCreate.txt`: `ACTION_A Type=5, SPHERE_TYPE=14` (salto),
`Type=1, SPHERE_TYPE=2, SPHERE_ACTOR2` (apuntar), y `Type=7` (interrumpir tarea previa).
El módulo que escribe estos campos es `src/compilar_secuencia.py`.
