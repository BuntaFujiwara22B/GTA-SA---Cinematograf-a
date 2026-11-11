# MVP: de una peticion a una caminata en Mission Maker

## Probar

```powershell
python main.py
```

1. Escribir: `Quiero que un personaje camine por una avenida grande durante 10 segundos`.
2. Pulsar Analizar. El plan aparece con su fuente: Gemini, Groq o reglas locales si las APIs no responden. Esta version admite una caminata recta de un solo personaje, no todas las acciones del catalogo.
3. Elegir al NPC en el carrusel. Si no se especifica un ID en el texto, la IA no lo elige automaticamente.
4. Deslizar al mapa. Para la primera prueba, pulsar **Usar avenida del ejemplo**. Reutiliza inicio/destino de ANIMA.mms. Para otra calle, seleccionar **Marcar inicio**, hacer clic, seleccionar **Marcar destino** y hacer clic en un punto cercano de la misma calle. Se validan distancias de 2 a 150 metros. El mapa no detecta anchura de avenidas, colisiones ni calcula rutas por las calles.
5. Deslizar a ambientacion. Elegir hora, clima y duracion (1 a 60 segundos). La camara disponible es **Fija elevada (ejemplo)**. POV y seguimiento aparecen deshabilitados hasta disponer de ejemplos reales.
6. En el mapa pulsar **Comprobar obstaculos en GTA**. Requiere una partida cargada, el script `comprobar_ruta_mvp.lua` instalado en MoonLoader y el jugador cerca de ambos puntos (menos de 150 m). Si detecta colision, cambiar los puntos y volver a comprobar: no se calcula un desvio automatico. Si GTA no responde, se indica que la ruta esta sin comprobar. Existe una opcion explicita para generar sin comprobacion, con advertencia; no permite ignorar una colision ya detectada.
7. Pulsar **Crear Mision (.MMS)**. La app abre su pantalla de resultado con la vista completa del archivo, **Copiar contenido**, **Guardar .mms como...** y **Volver a editar**. El dialogo de guardado permite elegir carpeta y nombre. Se conserva tambien una copia de trabajo y un JSON con las elecciones en `salida_mms`, sin reemplazar ANIMA.mms.
8. Guardar el `.mms` en `GTA San Andreas/modloader/SAMM(Stable)/ANIMACIONES` y cargarlo como se carga ANIMA.mms en Mission Maker. La generacion no inicia GTA ni importa la mision automaticamente.

## Comprobacion de obstaculos

Se consultan las colisiones cargadas en GTA mediante MoonLoader: lineas a tres alturas y tres posiciones laterales sobre segmentos de hasta 2 m. Incluye edificios, objetos y vehiculos, pero no peatones. Un resultado libre significa que esas lineas no encontraron colision, no que exista una ruta navegable garantizada. No comprueba todo el volumen del cuerpo ni elementos sin colision, huecos o cambios posteriores del trafico. El jugador debe estar cerca para reducir el riesgo de consultar una zona descargada; no es una prueba exhaustiva del streaming. Se exige repetir al cambiar inicio o destino.

La app tambien revisa cambios bruscos de altura a lo largo de la ruta. Esto puede advertir desniveles, pero por si solo no detecta vallas o muros. Si el juego esta cerrado, pausado o no tiene el script, la app nunca da por comprobada la ruta. Reiniciar GTA despues de instalar el script.

El puente intercambia una solicitud y respuesta correlacionadas por ID en `ruta_mvp`. La ubicacion del proyecto esta configurada en el Lua: actualizarla si se mueve el proyecto. La sintaxis Lua y el flujo de mensajes se han comprobado; falta la prueba funcional dentro de GTA con la valla concreta del usuario.

## Como funciona

Peticion -> plan estructurado con IA y candidatas del catalogo -> elecciones del usuario -> validacion -> exportador determinista -> MMS.

El planificador usa las descripciones ya analizadas y pistas locales del catalogo para contexto; no reenvia todas las fotos. Caminar se implementa con la tarea de ruta que ya existe en el ejemplo del usuario, no con un clip de caminar inventado. El archivo se genera a partir de `templates/caminar_referencia.mms`, conservando Type=4, POINT_MODE1=1, LOG1=MMS194 y LOG2=MMS253. El actor, puntos, orientacion, camara, hora, clima y duracion se parametrizan.

Las nuevas exportaciones usan `SHOW_INTRO=0`, dejan vacios `MPASS/MFAIL` y activan `HUD_OFF`, `RADAR_OFF` y los interruptores individuales del HUD en OBJ_0 y OBJ_1. Estas claves se localizaron en el main.scm del mod instalado; su efecto final se debe comprobar jugando la nueva exportacion, no reutilizando una anterior.

Actualizacion de clima: hora, minutos, clima y congelacion se escriben tambien en OBJ_1, igual que en las misiones de captura `clima_hora*.mms` del usuario. Los IDs se muestran con su nombre real: 9 es niebla y 10 es soleado de Las Venturas. Las fotos antiguas no se asignan por indice: solo se muestran si estan asociadas explicitamente a hora e ID en `assets/climas_catalogo.json` y marcadas como verificadas. Mientras no haya esa asociacion, se muestra un icono y el nombre del clima; las fotos originales no se borran. MPASS/MFAIL ahora usan `~n~` (texto de formato sin glifos) para evitar el mensaje por defecto que aparecia con valores vacios; falta comprobar este detalle en el juego.

Si el comprobador no responde, no es una colision detectada. GTA puede suspender la ejecucion al perder el foco. Pulsar comprobar, volver a la partida activa durante unos segundos y despues regresar a la app; el plazo de espera es 35 segundos. Este estado aparece en naranja; solo una colision reportada por el juego aparece en rojo. Elegir generar sin comprobacion actualiza el aviso sin afirmar que la ruta este libre.

La sugerencia de campo ya no usa (200,-100), donde la prueba mostro viviendas. Se usa otra semilla rural y se rechazan desniveles fuertes y superficies que sobresalen respecto a varios puntos vecinos. Es una heuristica: un tejado grande puede parecer terreno plano y el mapa no aporta una clasificacion fiable de edificios. No se debe interpretar una sugerencia como un suelo libre comprobado; sigue siendo necesaria la comprobacion en GTA.

La camara mantiene la posicion relativa y el punto de mirada del ejemplo, trasladados y rotados con la direccion de la nueva ruta. Los angulos se calculan a partir de la posicion y del objetivo. El encuadre esta pensado para una ruta corta como la del ejemplo; una ruta larga puede salir del plano.

La duracion controla `DIAL_TIME`, es decir, cuanto dura el plano. No cambia automaticamente la velocidad de caminar ni garantiza que el NPC siga moviendose hasta el ultimo segundo si llega antes al destino.

## Validacion y limites reales

- Siete pruebas automatizadas cubren planificacion, rechazos de alcance, ruta, angulos, limites, CRLF y recorrido completo de la interfaz hasta crear un archivo. Ejecutar con `python -m unittest discover -s tests -p "test_*mvp.py" -v`.
- Se probo una peticion real: Gemini no respondio y Groq genero el plan; se exporto el MMS de demostracion en `salida_mms`.
- La altura del mapa en los puntos originales es 9.90 frente a 9.875 del archivo real; para la avenida del ejemplo se usan las alturas originales.
- Falta comprobar el resultado generado dentro de GTA. La sintaxis y geometria estan verificadas, no la reproduccion final del mod.
- Los campos `GAME_TIME`, `GAME_MTIME` y `GAME_WEATHER` existen en el ejemplo pero estaban vacios: el MVP los rellena con hora, minutos e ID de clima. Su efecto debe comprobarse en el juego. Las fotos del reloj se conservan como referencia orientativa; no se ha demostrado una correspondencia exacta entre cada foto y el ID de clima.
- Si faltan cuotas, se indica explicitamente que el plan se preparo con reglas locales. Las peticiones no soportadas se rechazan, no se convierten silenciosamente en una caminata.
- El seguimiento frontal/trasero y las demas animaciones requieren ejemplos de como los guarda Mission Maker antes de implementar sus campos.
